"""Minimal end-to-end demo of the Chromium SDK.

    python examples/quickstart.py
"""

from chromium_sdk import ChromiumClient

client = ChromiumClient(data_dir="./.demo_data")

# 1. (optional) create a proxy
proxy_code = client.proxy_create(
    proxy_name="demo-proxy", proxy_type="http",
    proxy_addr="127.0.0.1", proxy_port=7890,
)["code"]
print("proxy:", proxy_code)

# 2. create an environment (a random fingerprint is generated automatically)
code = client.env_create(
    name="demo-env",
    platform="Win32",
    proxy_code=proxy_code,
    remark="created by quickstart",
)["code"]
print("env:", code)

# 3. inspect the generated fingerprint on demand
print("fingerprint sample:", client.generate_fingerprint("MacIntel")["webgl_value"])

# 4. list
print("envs:", client.env_list()["total"])

# 5. open / status / close (requires a local Chrome / Chromium)
try:
    info = client.env_open(code)
    print("opened:", info)
    print("status:", client.env_status(code))
    client.env_close(code)
    print("closed")
except Exception as exc:  # noqa: BLE001
    print("open skipped:", exc)

client.close()
