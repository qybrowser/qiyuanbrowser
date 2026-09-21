# Automation examples for an existing SDK environment

Start Qiyuan Cloud Runtime on `127.0.0.1:9003`. Set `SERVICE_TOKEN` in `_api.py` and `_api.mjs` if Runtime uses `--service_token`. Replace each example's `CODE` with an environment code from `/open/env/list`; the scripts keep all parameters in source. Each example calls `/open/env/open`, operates on that same browser instance, and calls `/open/env/close` in `finally`.

| Kernel | Example | Install | Connection |
| --- | --- | --- | --- |
| Chromium | `chromium_puppeteer.mjs` | `npm.cmd install (from SDK root)` | Puppeteer CDP |
| Chromium | `chromium_selenium.py` | `pip install selenium` | Selenium `debugger_address` |
| Chromium | `chromium_playwright.py` | `pip install playwright` | Playwright `connect_over_cdp` |
| Firefox | `firefox_puppeteer.mjs` | `npm.cmd install (from SDK root)` | Puppeteer WebDriver BiDi |
| Firefox | `firefox_bidi.py` | `pip install websockets` | Direct WebDriver BiDi commands |
| Chromium | `chromium_inject_js.mjs` | `npm.cmd install (from SDK root)` | Inject JS through Puppeteer CDP |
| Firefox | `firefox_inject_js.mjs` | `npm.cmd install (from SDK root)` | Inject JS through Puppeteer BiDi |

The Selenium example reads the opened Chromium version from CDP, reuses a matching driver from `%USERPROFILE%\.cache\qiyuan-cloud-sdk\chromedriver`, or downloads one from the official Chrome for Testing index. Set `CHROMEDRIVER_PATH` in `chromium_selenium.py` to a matching local executable when offline. The ChromeDriver major version must match the browser major version.

Run one file at a time, for example `python chromium_playwright.py` or `node firefox_puppeteer.mjs`. Each opens `https://example.com`, reads the page title, and closes the environment. They attach to the browser opened by Runtime. Puppeteer is a JavaScript library; Selenium's normal Firefox driver flow launches a separate browser, so it is intentionally not used for the existing Firefox environment. Playwright's `firefox.connect()` expects a Playwright server endpoint and cannot connect to Runtime's BiDi `/session` endpoint.

Puppeteer Firefox uses BiDi support and may depend on the installed Puppeteer and Qiyuan Firefox versions. If that connection is rejected, use the direct BiDi example and inspect the returned protocol/error; these examples do not silently fall back to launching another Firefox.

The injection examples run with `node chromium_inject_js.mjs` or `node firefox_inject_js.mjs`. They show pre-navigation injection (`evaluateOnNewDocument`), page-side JS (`evaluate`), DOM and session storage access, inline/external script tags (`addScriptTag`), and an optional `fetch`. Set `CROSS_ORIGIN_URL` or `EXTERNAL_SCRIPT_URL` in the source to try those optional steps. Page-side JS has the visited page's origin and browser permissions. Cross-origin `fetch` can send a request, but JavaScript can read the response only when the destination permits it with CORS; the page's CSP and network rules may also block it. `credentials: 'omit'` avoids sending cookies in this example. Injecting JS does not bypass CORS. For a server-to-server API call without page CORS, make the HTTP request from Node or Python outside `page.evaluate()`; that request does not inherit the page's cookies or origin.

Protocol references: [Puppeteer connect options](https://pptr.dev/api/puppeteer.connectoptions), [Playwright Python CDP connection](https://playwright.dev/python/docs/api/class-browsertype), and [Firefox BiDi connection](https://developer.mozilla.org/en-US/docs/Web/WebDriver/How_to/Create_BiDi_connection).
