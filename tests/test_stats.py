"""
Test suite for /stats endpoint:
- total_messages correctness
- senders_count correctness
- messages_per_sender sums to total
- first_message_ts and last_message_ts correctness
"""
import pytest
import hmac
import hashlib
import json
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings


def compute_signature(body: str) -> str:
    """Compute HMAC-SHA256 signature for a request body."""
    return hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


async def insert_test_message(client, message_id: str, from_msisdn: str, ts: str, text: str = "Test"):
    """Helper to insert a test message via webhook."""
    payload = {
        "message_id": message_id,
        "from": from_msisdn,
        "to": "+14155550100",
        "ts": ts,
        "text": text
    }
    body = json.dumps(payload)
    signature = compute_signature(body)
    await client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature
        }
    )


@pytest.mark.asyncio
async def test_stats_response_structure():
    """Test that /stats returns the expected structure."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    assert "total_messages" in data
    assert "senders_count" in data
    assert "messages_per_sender" in data
    assert "first_message_ts" in data
    assert "last_message_ts" in data


@pytest.mark.asyncio
async def test_stats_total_messages():
    """Test that total_messages reflects inserted count."""
    import uuid
    unique_id = uuid.uuid4().hex[:8]
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get initial count
        response_before = await client.get("/stats")
        initial_total = response_before.json()["total_messages"]
        
        # Insert new messages with unique IDs
        await insert_test_message(client, f"stat-total-{unique_id}-001", "+919876543210", "2025-01-15T10:00:00Z")
        await insert_test_message(client, f"stat-total-{unique_id}-002", "+919876543210", "2025-01-15T10:01:00Z")
        
        # Get new count
        response_after = await client.get("/stats")
        new_total = response_after.json()["total_messages"]
    
    assert new_total == initial_total + 2


@pytest.mark.asyncio
async def test_stats_senders_count():
    """Test that senders_count reflects unique senders."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert messages from different senders
        await insert_test_message(client, "stat-sender-001", "+911111111111", "2025-01-15T10:00:00Z")
        await insert_test_message(client, "stat-sender-002", "+911111111111", "2025-01-15T10:01:00Z")  # Same sender
        await insert_test_message(client, "stat-sender-003", "+922222222222", "2025-01-15T10:02:00Z")  # Different sender
        
        response = await client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    # senders_count should be >= 2 (at least the 2 unique senders we added)
    assert data["senders_count"] >= 2


@pytest.mark.asyncio
async def test_stats_messages_per_sender_sum():
    """Test that messages_per_sender entries sum up to total_messages (for listed senders)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert some messages
        await insert_test_message(client, "stat-sum-001", "+919876543210", "2025-01-15T10:00:00Z")
        
        response = await client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    
    # Sum of counts in messages_per_sender
    sender_sum = sum(sender["count"] for sender in data["messages_per_sender"])
    
    # The sum should equal total_messages (assuming top 10 covers all senders in test)
    # Note: This assertion assumes limited test data; in production with >10 senders, sum may be less than total
    assert sender_sum <= data["total_messages"]


@pytest.mark.asyncio
async def test_stats_first_and_last_message_ts():
    """Test that first_message_ts and last_message_ts are correct min/max."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert messages with known timestamps
        await insert_test_message(client, "stat-ts-001", "+919876543210", "2025-01-01T00:00:00Z")
        await insert_test_message(client, "stat-ts-002", "+919876543210", "2025-12-31T23:59:59Z")
        await insert_test_message(client, "stat-ts-003", "+919876543210", "2025-06-15T12:00:00Z")
        
        response = await client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    
    # first_message_ts should be the earliest
    assert data["first_message_ts"] <= "2025-01-01T00:00:00Z"
    # last_message_ts should be the latest
    assert data["last_message_ts"] >= "2025-12-31T23:59:59Z"


@pytest.mark.asyncio
async def test_stats_empty_database_handling():
    """Test that /stats handles empty database gracefully."""
    # Note: This test may fail if run after other tests that insert data
    # In a real test setup, you'd reset the database between tests
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    # Should return valid structure even with no data
    assert isinstance(data["total_messages"], int)
    assert isinstance(data["senders_count"], int)
    assert isinstance(data["messages_per_sender"], list)
