# Lyftr Webhook API

A FastAPI-based webhook receiver that accepts WhatsApp-style message payloads with HMAC-SHA256 signature verification, stores them in SQLite, and provides querying/analytics endpoints.

## Quick Start

### Prerequisites
- Docker & Docker Compose installed

### Running the Application

```bash
# Start the service (builds and runs in background)
make up

# View logs
make logs

# Stop and cleanup (removes volumes)
make down

# Run tests
make test
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health Checks
- **GET** `/health/live` - Liveness probe (always returns 200 when running)
- **GET** `/health/ready` - Readiness probe (checks DB connectivity)

### Webhook (Message Ingestion)
- **POST** `/webhook` - Receive and store messages
  - Requires `X-Signature` header with HMAC-SHA256 signature
  - Body: `{"message_id": "...", "from": "+...", "to": "+...", "ts": "ISO-8601", "text": "..."}`

### Query Endpoints
- **GET** `/messages` - Paginated message listing
  - Query params: `limit` (1-100, default 50), `offset` (default 0)
  - Filters: `from` (sender MSISDN), `since` (ISO-8601 timestamp), `q` (text search)
  - Ordering: `ts ASC, message_id ASC`

- **GET** `/stats` - Message analytics
  - Returns: `total_messages`, `senders_count`, `messages_per_sender`, `first_message_ts`, `last_message_ts`

### Observability
- **GET** `/metrics` - Prometheus metrics endpoint
  - Exposes: `http_requests_total`, `webhook_requests_total`, `request_latency_ms`

## Example Usage

### Send a webhook message

```bash
# Set your secret
export WEBHOOK_SECRET="testsecret"

# Prepare payload
BODY='{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'

# Compute signature
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $2}')

# Send request
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIG" \
  -d "$BODY"
```

### Query messages

```bash
# List all messages
curl http://localhost:8000/messages

# With pagination
curl "http://localhost:8000/messages?limit=10&offset=0"

# Filter by sender
curl "http://localhost:8000/messages?from=+919876543210"

# Filter by time
curl "http://localhost:8000/messages?since=2025-01-15T09:00:00Z"

# Search by text
curl "http://localhost:8000/messages?q=Hello"
```

### Get statistics

```bash
curl http://localhost:8000/stats
```

## Design Decisions

### HMAC Signature Verification
- Signatures are verified using HMAC-SHA256
- The raw request body bytes are used for signature computation (preserves exact payload)
- Signature comparison uses `hmac.compare_digest()` for timing-attack resistance
- Missing or invalid signatures return HTTP 401

### Pagination Contract
- Response format: `{"data": [...], "total": N, "limit": N, "offset": N}`
- `total` reflects the count for the applied filters (not just the page)
- `limit` defaults to 50, constrained to 1-100
- Results ordered by `ts ASC, message_id ASC` for deterministic pagination

### Idempotency
- Enforced via `PRIMARY KEY (message_id)` in SQLite
- Duplicate detection at app layer before insert (avoids DB constraint errors)
- Duplicate requests return HTTP 200 (idempotent success)

### Metrics Definition
- `http_requests_total{path, status}` - All HTTP requests
- `webhook_requests_total{result}` - Webhook outcomes (created, duplicate, invalid_signature, validation_error)
- `request_latency_ms` - Request processing time histogram

### Logging
- Structured JSON logs (one valid JSON object per line)
- Includes: `ts`, `level`, `request_id`, `method`, `path`, `status`, `latency_ms`
- Webhook logs include: `message_id`, `dup`, `result`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBHOOK_SECRET` | (required) | Secret key for HMAC signature verification |
| `DATABASE_URL` | `sqlite:////data/app.db` | SQLite database connection URL |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Project Structure

```
/app
  main.py            # FastAPI app, middleware, routes
  models.py          # Pydantic models
  storage.py         # SQLite operations
  logging_utils.py   # JSON logger
  metrics.py         # Prometheus metrics
  config.py          # Environment configuration
/tests
  test_webhook.py    # Webhook endpoint tests
  test_messages.py   # Pagination & filter tests
  test_stats.py      # Statistics tests
Dockerfile           # Multi-stage build
docker-compose.yml   # Service configuration
Makefile             # Dev commands
```

## Setup Used

VSCode + Windsurf Cascade AI assistant