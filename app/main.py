import time
import uuid
import logging
import aiosqlite
from fastapi import FastAPI, Request, Response, HTTPException, Header
from contextlib import asynccontextmanager
import hmac
import hashlib
import json
from datetime import datetime, timezone

from app.config import settings
from app.storage import init_db, insert_message
from app.logging_utils import setup_logging
from app.models import WebhookPayload
from typing import Optional
from fastapi import Query
from app.models import MessageResponse, StatsResponse
from app.storage import get_messages, get_stats
from app.metrics import HTTP_REQUESTS_TOTAL, WEBHOOK_REQUESTS_TOTAL, REQUEST_LATENCY, get_metrics_output

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("api")

# Lifespan Events: The modern way to run startup/shutdown code in FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized", extra={"extra_data": {"event": "startup"}})
    yield

app = FastAPI(title="Lyftr Webhook API", lifespan=lifespan)

# Middleware wrapper
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Intercepts every request to log structured data.
    """
    # A. Start Timer & Generate ID
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Store request_id in state so endpoints can use it if needed
    request.state.request_id = request_id
    status_code = 500

    # B. Process the Request (Call the actual endpoint)
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        # If the app crashes, we still want to log it
        process_time = (time.time() - start_time) * 1000
        logger.error(
            "Request failed",
            extra={
                "extra_data": {
                    "ts": datetime.now(timezone.utc).isoformat(), # Redundant but safe
                    "level": "ERROR",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": 500,
                    "latency_ms": round(process_time, 2),
                    "error": str(e)
                }
            }
        )
        raise e
    finally:
        # --- METRICS LOGIC ---
        process_time = (time.time() - start_time) * 1000
        
        # 1. Record Latency
        REQUEST_LATENCY.observe(process_time)
        
        # 2. Record HTTP Count
        # We group all /messages?q=... into just "/messages" to avoid infinite labels
        path = request.url.path
        HTTP_REQUESTS_TOTAL.labels(path=path, status=str(status_code)).inc()

        # 3. Record Webhook Specifics
        # If the endpoint set a 'result' in state, record it
        if hasattr(request.state, "result"):
            WEBHOOK_REQUESTS_TOTAL.labels(result=request.state.result).inc()


    if status_code < 500:
            extra_fields = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "latency_ms": round(process_time, 2),
            }
            
            if hasattr(request.state, "message_id"):
                extra_fields["message_id"] = request.state.message_id
            if hasattr(request.state, "dup"):
                extra_fields["dup"] = request.state.dup
            if hasattr(request.state, "result"):
                extra_fields["result"] = request.state.result

            logger.info(
                "Request processed", 
                extra={"extra_data": extra_fields}
            )
            
    return response


async def verify_signature(request: Request, body_bytes: bytes):
    """
    Calculates HMAC-SHA256 and compares it with X-Signature header.
    Raises 401 if invalid or if no secret is configured.
    """
    # If no secret is configured, reject all requests
    if not settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Webhook secret not configured")
    
    # Get the header
    x_signature = request.headers.get("X-Signature")
    if not x_signature:
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Calculate expected signature
    secret_bytes = settings.WEBHOOK_SECRET.encode("utf-8")
    expected_signature = hmac.new(
        secret_bytes,
        body_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures
    if not hmac.compare_digest(x_signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    

@app.get("/health/live")
async def liveness_probe():
    """
    Always return 200 once the app is running.
    """
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness_probe():
    """
    Checks if DB is reachable.
    """
    try:
        # Try to run a simple query
        from app.storage import get_db_path
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute("SELECT 1")
        return {"status": "ready"}
    except Exception:
        # If DB fails, return 503 Service Unavailable
        raise HTTPException(status_code=503, detail="Database unavailable")
    
@app.get("/metrics")
async def metrics():
    data, content_type = get_metrics_output()
    return Response(content=data, media_type=content_type)


@app.get("/")
async def root():
    return {
        "message": "Webhook API is running",
        "config_check": f"Secret is configured: {bool(settings.WEBHOOK_SECRET)}"
    }

# Webhook Endpoint
@app.post('/webhook')
async def receive_webhook(request: Request):
    # Read raw bytes
    body_bytes = await request.body()

    try:
        await verify_signature(request, body_bytes)
    except HTTPException as e:
        # Log the failure before returning error
        request.state.result = "invalid_signature"
        raise e
    
    # Parse JSON manually
    # we can use pydantic argument (payload: WebhookPayload) directly
    # because we already consumed the body stream to get bytes.
    try:
        # Handle empty body
        if not body_bytes:
            request.state.result = "validation_error"
            raise HTTPException(status_code=422, detail="Empty request body")
        
        # Decode bytes to string (handle non-UTF8)
        try:
            body_str = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            request.state.result = "validation_error"
            raise HTTPException(status_code=422, detail="Invalid UTF-8 encoding")
        
        # Parse JSON
        try:
            json_data = json.loads(body_str)
        except json.JSONDecodeError as e:
            request.state.result = "validation_error"
            raise HTTPException(status_code=422, detail=f"Invalid JSON: {str(e)}")
        
        # Validate that json_data is a dict (not list, string, etc.)
        if not isinstance(json_data, dict):
            request.state.result = "validation_error"
            raise HTTPException(status_code=422, detail="Request body must be a JSON object")
        
        # Validate with Pydantic
        payload = WebhookPayload(**json_data)
    except HTTPException:
        raise
    except Exception as e:
        request.state.result = "validation_error"
        raise HTTPException(status_code=422, detail=str(e))

    # Populate logging context
    request.state.message_id = payload.message_id

    # Database operation
    status = await insert_message(payload)

    # update logging context
    request.state.result = status
    request.state.dup = (status == "duplicate")

    return {"status": "ok"}

@app.get("/messages")
async def list_messages(
    limit: int = Query(50, ge=1, le=100), # Default 50, Min 1, Max 100
    offset: int = Query(0, ge=0),         # Default 0, Min 0
    from_msisdn: Optional[str] = Query(None, alias="from"), # Map ?from= to from_msisdn
    since: Optional[str] = None,
    q: Optional[str] = None
):
    """
    Paginated list of messages with filters.
    """
    result = await get_messages(
        limit=limit, 
        offset=offset, 
        from_msisdn=from_msisdn, 
        since=since, 
        q=q
    )
    
    # We return the raw dict, but we could wrap it in a Pydantic model if we wanted strict validation here too.
    # For now, we return the shape { "data": [...], "total": N, "limit": N, "offset": N }
    return {
        "data": result["data"],
        "total": result["total"],
        "limit": limit,
        "offset": offset
    }

@app.get("/stats", response_model=StatsResponse)
async def get_analytics():
    """
    Returns message statistics.
    """
    stats = await get_stats()
    return stats