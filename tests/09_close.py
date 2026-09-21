"""POST /open/env/close: close one already-running test environment."""

from _client import call, require_code

CODE = "REPLACE_WITH_RUNNING_ENV_CODE"

if __name__ == "__main__":
    call("/open/env/close", {"code": require_code(CODE)})
    print("OK: environment closed")
