"""GET /open/env/list: list environments and inspect kernel defaults."""

from urllib.parse import urlencode
from _client import call

PAGE = 1
PAGE_SIZE = 100
KEYWORD = ""

if __name__ == "__main__":
    query = urlencode({"page": PAGE, "page_size": PAGE_SIZE, "keyword": KEYWORD})
    data = call(f"/open/env/list?{query}")
    assert isinstance(data.get("items"), list), "items must be a list"
    for item in data["items"]:
        assert item["browser_kernel"] in ("chrome", "firefox"), item
    print(f"OK: {len(data['items'])} environments on this page")
