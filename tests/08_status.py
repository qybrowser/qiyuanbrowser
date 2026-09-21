"""GET /open/env/status: inspect one test environment in this Runtime."""

from urllib.parse import urlencode
from _client import call, require_code

CODE = "d72cd8bd2209e2697b28234efaead8d1"

if __name__ == "__main__":
    code = require_code(CODE)
    data = call("/open/env/status?" + urlencode({"code": code}))
    assert data["code"] == code, data
    assert data["status"] in ("running", "stopped"), data
    print("OK: environment status", data["status"])
