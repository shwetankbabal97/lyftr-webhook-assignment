from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# 1. HTTP Request Counter
# Labels: path (e.g., /webhook), status (e.g., 200, 401)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["path", "status"]
)

# 2. Webhook Outcome Counter
# Labels: result (created, duplicate, invalid_signature, validation_error)
WEBHOOK_REQUESTS_TOTAL = Counter(
    "webhook_requests_total",
    "Total number of webhook processing outcomes",
    ["result"]
)

# 3. Latency Histogram
# We use default buckets, but you can customize them
REQUEST_LATENCY = Histogram(
    "request_latency_ms",
    "Request latency in milliseconds",
    buckets=[100, 500, float("inf")] # <100ms, <500ms, >500ms
)

def get_metrics_output():
    """
    Returns the metrics in the format Prometheus expects.
    """
    return generate_latest(), CONTENT_TYPE_LATEST