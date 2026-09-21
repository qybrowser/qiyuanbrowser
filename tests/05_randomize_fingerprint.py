"""POST /open/env/randomize_fingerprint: regenerate a test fingerprint."""

from _client import call, require_code

CODE = "d72cd8bd2209e2697b28234efaead8d1"

if __name__ == "__main__":
    data = call("/open/env/randomize_fingerprint", {"code": require_code(CODE)})
    assert isinstance(data, dict), "fingerprint response must be an object"
    print("OK: fingerprint randomized")
