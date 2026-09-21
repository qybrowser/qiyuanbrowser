"""POST /open/env/create: create a Firefox environment."""

from _client import call

NAME = "SDK-API-Firefox-Test"
BROWSER_KERNEL = "firefox"
# Omit browser_version to use the latest Firefox runtime in the SDK manifest.

if __name__ == "__main__":
    data = call("/open/env/create", {"name": NAME, "browser_kernel": BROWSER_KERNEL})
    assert data.get("code"), "create must return an environment code"
    print("Save this Firefox code for 07_open_firefox.py:", data["code"])
