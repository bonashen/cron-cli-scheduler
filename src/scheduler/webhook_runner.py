"""Webhook runner - sends webhook notifications in background."""

from __future__ import annotations

import json
import logging
import os
import sys

logging.basicConfig(level=logging.WARNING)


def main() -> None:
    url = os.environ.get("WEBHOOK_URL")
    token = os.environ.get("WEBHOOK_TOKEN", "")
    payload_str = os.environ.get("WEBHOOK_PAYLOAD", "{}")
    
    if not url:
        sys.exit(1)
    
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        payload = {}
    
    try:
        import urllib.request
        import urllib.error
        
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if 200 <= response.status < 300:
                sys.exit(0)
            else:
                sys.exit(1)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
