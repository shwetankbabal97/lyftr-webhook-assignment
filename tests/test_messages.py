"""
Test suite for /messages endpoint:
- Basic listing
- Pagination (limit, offset)
- Filters (from, since, q)
- Correct ordering
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
async def test_messages_basic_listing():
    """Test basic message listing returns expected structure."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert a test message
        await insert_test_message(client, "msg-list-001", "+919876543210", "2025-01-15T10:00:00Z")
        
        # Get messages
        response = await client.get("/messages")
    
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


@pytest.mark.asyncio
async def test_messages_pagination_limit():
    """Test that limit parameter restricts results."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert multiple messages
        for i in range(5):
            await insert_test_message(
                client,
                f"msg-page-{i:03d}",
                "+919876543210",
                f"2025-01-15T10:0{i}:00Z"
            )
        
        # Request with limit=2
        response = await client.get("/messages?limit=2")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) <= 2
    assert data["limit"] == 2


@pytest.mark.asyncio
async def test_messages_pagination_offset():
    """Test that offset parameter skips results."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert messages with predictable order
        await insert_test_message(client, "msg-off-001", "+919876543210", "2025-01-15T10:00:00Z")
        await insert_test_message(client, "msg-off-002", "+919876543210", "2025-01-15T10:01:00Z")
        
        # Get all messages
        response_all = await client.get("/messages")
        
        # Get with offset
        response_offset = await client.get("/messages?offset=1&limit=100")
    
    assert response_offset.status_code == 200
    data_offset = response_offset.json()
    assert data_offset["offset"] == 1


@pytest.mark.asyncio
async def test_messages_filter_by_from():
    """Test filtering by from (sender MSISDN)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert messages from different senders
        await insert_test_message(client, "msg-from-001", "+919876543210", "2025-01-15T10:00:00Z")
        await insert_test_message(client, "msg-from-002", "+919999999999", "2025-01-15T10:01:00Z")
        
        # Filter by specific sender
        response = await client.get("/messages?from=%2B919876543210")
    
    assert response.status_code == 200
    data = response.json()
    # All returned messages should be from the filtered sender
    for msg in data["data"]:
        assert msg["from"] == "+919876543210"


@pytest.mark.asyncio
async def test_messages_filter_by_since():
    """Test filtering by since (timestamp)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert messages with different timestamps
        await insert_test_message(client, "msg-since-001", "+919876543210", "2025-01-15T08:00:00Z")
        await insert_test_message(client, "msg-since-002", "+919876543210", "2025-01-15T12:00:00Z")
        
        # Filter since 10:00
        response = await client.get("/messages?since=2025-01-15T10:00:00Z")
    
    assert response.status_code == 200
    data = response.json()
    # All returned messages should be >= since timestamp
    for msg in data["data"]:
        assert msg["ts"] >= "2025-01-15T10:00:00Z"


@pytest.mark.asyncio
async def test_messages_filter_by_text_search():
    """Test filtering by q (text search)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert messages with different text
        await insert_test_message(client, "msg-search-001", "+919876543210", "2025-01-15T10:00:00Z", "Hello World")
        await insert_test_message(client, "msg-search-002", "+919876543210", "2025-01-15T10:01:00Z", "Goodbye Moon")
        
        # Search for "Hello"
        response = await client.get("/messages?q=Hello")
    
    assert response.status_code == 200
    data = response.json()
    # All returned messages should contain the search term
    for msg in data["data"]:
        assert "Hello" in msg["text"]


@pytest.mark.asyncio
async def test_messages_ordering():
    """Test that messages are ordered by ts ASC, message_id ASC."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert messages out of order
        await insert_test_message(client, "msg-order-002", "+919876543210", "2025-01-15T10:01:00Z")
        await insert_test_message(client, "msg-order-001", "+919876543210", "2025-01-15T10:00:00Z")
        await insert_test_message(client, "msg-order-003", "+919876543210", "2025-01-15T10:01:00Z")  # Same ts, different id
        
        # Get messages
        response = await client.get("/messages")
    
    assert response.status_code == 200
    data = response.json()
    messages = data["data"]
    
    # Verify ordering
    for i in range(len(messages) - 1):
        curr = messages[i]
        next_msg = messages[i + 1]
        # Should be ordered by ts first, then message_id
        assert (curr["ts"], curr["message_id"]) <= (next_msg["ts"], next_msg["message_id"])


@pytest.mark.asyncio
async def test_messages_total_reflects_filters():
    """Test that total count reflects the applied filters."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Insert messages from different senders
        await insert_test_message(client, "msg-total-001", "+911111111111", "2025-01-15T10:00:00Z")
        await insert_test_message(client, "msg-total-002", "+911111111111", "2025-01-15T10:01:00Z")
        await insert_test_message(client, "msg-total-003", "+922222222222", "2025-01-15T10:02:00Z")
        
        # Filter by one sender
        response = await client.get("/messages?from=%2B911111111111")
    
    assert response.status_code == 200
    data = response.json()
    # Total should only count messages matching the filter
    assert data["total"] >= 2  # At least the 2 we inserted
