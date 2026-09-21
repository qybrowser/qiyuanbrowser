"""Attach Playwright to the existing Chromium environment over CDP."""

from playwright.sync_api import sync_playwright
from _api import close_browser, open_browser

CODE = "55f0cc0858c60ddaaa52f363729a040b"
URL = "https://example.com"

if __name__ == "__main__":
    opened = open_browser(CODE, "chrome")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(opened["debug_endpoint"])
            try:
                context = browser.contexts[0]
                page = context.new_page()
                page.goto(URL, wait_until="domcontentloaded")
                print({"kernel": opened["browser_kernel"], "title": page.title(), "url": page.url})
            finally:
                browser.close()
    finally:
        close_browser(CODE)
