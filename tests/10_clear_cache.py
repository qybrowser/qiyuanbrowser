"""POST /open/env/clear_cache: remove profile data from a disposable test environment."""

from _client import call, require_code

CODE = "REPLACE_WITH_DISPOSABLE_ENV_CODE"

if __name__ == "__main__":
    call("/open/env/clear_cache", {"code": require_code(CODE)})
    print("OK: environment cache cleared")
