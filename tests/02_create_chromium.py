"""POST /open/env/create: create a Chromium environment."""

from _client import call

NAME = "SDK-API-Chromium-Test"
BROWSER_KERNEL = "chrome"
# Omit browser_version to use the latest Chrome runtime in the SDK manifest.

if __name__ == "__main__":
    data = call("/open/env/create", {"name": NAME, "browser_kernel": BROWSER_KERNEL})
    assert data.get("code"), "create must return an environment code"
    print("Save this Chromium code for 06_open_chromium.py:", data["code"])
