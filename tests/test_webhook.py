"""
Test suite for webhook endpoint:
- Valid insert
- Duplicate handling (idempotency)
- Signature validation cases
"""
import pytest
import hmac
import hashlib
import json
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings


def compute_signature(body: str, secret: str = None) -> str:
    """Compute HMAC-SHA256 signature for a request body."""
    if secret is None:
        secret = settings.WEBHOOK_SECRET
    return hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


@pytest.fixture
def valid_payload():
    return {
        "message_id": "test-msg-001",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello from test"
    }


@pytest.mark.asyncio
async def test_webhook_valid_insert(valid_payload):
    """Test that a valid webhook request inserts the message and returns 200."""
    body = json.dumps(valid_payload)
    signature = compute_signature(body)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_webhook_duplicate_returns_200(valid_payload):
    """Test that duplicate message_id returns 200 (idempotent)."""
    # Use unique message_id for this test
    valid_payload["message_id"] = "test-dup-001"
    body = json.dumps(valid_payload)
    signature = compute_signature(body)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First request - should create
        response1 = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
        
        # Second request with same message_id - should be duplicate
        response2 = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
    
    assert response1.status_code == 200
    assert response2.status_code == 200  # Idempotent - still returns 200


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_401(valid_payload):
    """Test that invalid signature returns 401."""
    body = json.dumps(valid_payload)
    invalid_signature = "invalid123"
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": invalid_signature
            }
        )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_missing_signature_returns_401(valid_payload):
    """Test that missing X-Signature header returns 401."""
    body = json.dumps(valid_payload)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json"}
        )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_invalid_json_returns_422():
    """Test that invalid JSON returns 422."""
    body = "not valid json"
    signature = compute_signature(body)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_webhook_missing_required_field_returns_422():
    """Test that missing required fields returns 422."""
    incomplete_payload = {
        "message_id": "test-incomplete",
        "from": "+919876543210"
        # Missing: to, ts
    }
    body = json.dumps(incomplete_payload)
    signature = compute_signature(body)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
    
    assert response.status_code == 422