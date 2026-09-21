"""POST /open/env/delete: delete a disposable test environment."""

from _client import call, require_code

CODE = "REPLACE_WITH_DISPOSABLE_ENV_CODE"

if __name__ == "__main__":
    call("/open/env/delete", {"code": require_code(CODE)})
    print("OK: environment deleted")
