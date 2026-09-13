"""Send one synthetic OTLP/HTTP trace to the local blog example Collector."""

import json
import secrets
import time
import urllib.request
import uuid


def main():
    trace_id = uuid.uuid4().hex
    ended = time.time_ns()
    payload = {
        "resourceSpans": [{
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": "ml-collector-demo"}},
                {"key": "deployment.environment.name", "value": {"stringValue": "local"}},
            ]},
            "scopeSpans": [{
                "scope": {"name": "polyaxon-blog-example"},
                "spans": [{
                    "traceId": trace_id,
                    "spanId": secrets.token_hex(8),
                    "name": "synthetic-model-request",
                    "kind": 2,
                    "startTimeUnixNano": str(ended - 1_000_000),
                    "endTimeUnixNano": str(ended),
                    "attributes": [
                        {"key": "ml.operation.id", "value": {"stringValue": "example-operation"}},
                        {"key": "user.email", "value": {"stringValue": "synthetic@example.invalid"}},
                    ],
                    "status": {"code": 1},
                }],
            }],
        }],
    }
    request = urllib.request.Request(
        "http://127.0.0.1:4318/v1/traces",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.loads(response.read().decode("utf-8") or "{}")
    partial = result.get("partialSuccess", {})
    if int(partial.get("rejectedSpans", 0)) or partial.get("errorMessage"):
        raise RuntimeError(f"Collector reported partial success: {partial}")
    print(f"Collector accepted trace {trace_id}; check its exporter output next.")


if __name__ == "__main__":
    main()
