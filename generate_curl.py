import hmac
import hashlib
import json
import sys

# 1. The Secret (MUST match what you exported in your terminal)
SECRET = "testsecret" 

# 2. The Data you want to send
# You can change these values here to generate different test cases
data = {
    "message_id": "m4",  # Change this to m3, m4...
    "from": "+1",
    "to": "+2",
    "ts": "2025-01-02T00:00:00Z",
    "text": "Stop"
}

# 3. Convert to JSON string (Compact, no spaces)
# separators=(',', ':') ensures it looks like {"a":1} not {"a": 1}
body = json.dumps(data, separators=(',', ':'))

# 4. Calculate Signature
sig = hmac.new(
    SECRET.encode("utf-8"), 
    body.encode("utf-8"), 
    hashlib.sha256
).hexdigest()

# 5. Print the Command
print(f"\nCopy and run this command:\n")
print(f"curl -v -X POST http://localhost:8000/webhook \\")
print(f'  -H "Content-Type: application/json" \\')
print(f'  -H "X-Signature: {sig}" \\')
print(f"  -d '{body}'")
print("\n")