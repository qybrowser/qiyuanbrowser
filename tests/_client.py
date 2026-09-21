"""Shared HTTP client for manually run environment API checks."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:9003"
SERVICE_TOKEN = ""  # Fill only when Runtime started with --service_token.
TIMEOUT_SECONDS = 45


def require_code(code):
    if not code or code.startswith("REPLACE_"):
        raise ValueError("Replace the CODE constant in this test with a real environment code")
    return code


def call(path, body=None):
    headers = {"Content-Type": "application/json"}
    if SERVICE_TOKEN:
        headers["X-Qiyuan-Runtime-Token"] = SERVICE_TOKEN
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = Request(BASE_URL + path, data=payload, headers=headers)
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            result = json.load(response)
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"Request failed: {path}: {error}") from error
    if not isinstance(result, dict) or not result.get("success"):
        raise RuntimeError(f"API failed: {path}: {result}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result.get("data")
