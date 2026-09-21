# Environment HTTP interface checks

Start the Qiyuan Cloud Runtime on `127.0.0.1:9003`, then run each script separately with Python 3.10+ (standard library only). Set `BASE_URL` and, if used, `SERVICE_TOKEN` in `_client.py`. Every request parameter is a constant in the relevant script.

Run `02_create_chromium.py` and `03_create_firefox.py` to obtain environment codes. Paste those codes into the `CODE` constants of `06_open_chromium.py` and `07_open_firefox.py`. Other scripts also require a real test environment code. A `REPLACE_...` code is rejected before any request.

Each script covers one `/open/env/*` route. The create and open routes have separate Chromium and Firefox cases. The open scripts use visible windows, verify the returned protocol and live debug endpoint, and close the browser after you press Enter. `09_close.py` requires an already-running environment. `05_randomize_fingerprint.py`, `10_clear_cache.py`, and `11_delete.py` modify or remove environment data, so point them at disposable test environments. No script runs automatically.
