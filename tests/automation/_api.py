"""Local Runtime helper for the Python automation examples."""

import json
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:9003"
SERVICE_TOKEN = ""  # Set this if Runtime was started with --service_token.


def api(path, body):
    headers = {"Content-Type": "application/json"}
    if SERVICE_TOKEN:
        headers["X-Qiyuan-Runtime-Token"] = SERVICE_TOKEN
    request = Request(BASE_URL + path, data=json.dumps(body).encode(), headers=headers)
    with urlopen(request, timeout=45) as response:
        result = json.load(response)
    if not result.get("success"):
        raise RuntimeError(result.get("error", result))
    return result.get("data")


def open_browser(code, kernel):
    if code.startswith("REPLACE_"):
        raise ValueError("Replace CODE with the environment code from /open/env/list")
    data = api("/open/env/open", {"code": code, "headless": False, "needDebugPort": True})
    expected_protocol = "cdp" if kernel == "chrome" else "webdriver-bidi"
    if data["browser_kernel"] != kernel or data["debug_protocol"] != expected_protocol or not data["debug_endpoint"]:
        api("/open/env/close", {"code": code})
        raise RuntimeError(f"Unexpected browser/debug protocol: {data}")
    return data


def close_browser(code):
    api("/open/env/close", {"code": code})
