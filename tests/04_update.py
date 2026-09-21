"""POST /open/env/update: change a test environment remark."""

from _client import call, require_code

CODE = "REPLACE_WITH_TEST_ENV_CODE"
REMARK = "updated by SDK environment API check"

if __name__ == "__main__":
    call("/open/env/update", {"code": require_code(CODE), "remark": REMARK})
    print("OK: environment remark updated")
