"""POST /open/env/open: open Chromium, verify CDP, then close on Enter."""

import json
from urllib.request import urlopen
from _client import call, require_code

CODE = "55f0cc0858c60ddaaa52f363729a040b"
HEADLESS = False
OPEN_TABS = False
NEED_DEBUG_PORT = True
ARGS = []

if __name__ == "__main__":
    code = require_code(CODE)
    opened = call("/open/env/open", {"code": code, "headless": HEADLESS,
                                     "openTabs": OPEN_TABS, "needDebugPort": NEED_DEBUG_PORT, "args": ARGS})
    try:
        assert opened["pid"] > 0
        assert opened["browser_kernel"] == "chrome", opened
        assert opened["debug_protocol"] == "cdp", opened
        assert opened["debug_port"] > 0
        assert opened["debug_endpoint"] == f"http://127.0.0.1:{opened['debug_port']}"
        with urlopen(opened["debug_endpoint"] + "/json/version", timeout=5) as response:
            version = json.load(response)
        assert isinstance(version, dict), version
        print("CDP /json/version:", json.dumps(version, ensure_ascii=False, indent=2))
        print("Chromium window is open. Press Enter to close it.")
        input()
    finally:
        call("/open/env/close", {"code": code})
