"""Shared records are fetched over HTTP by a client without a local SQLite DB."""
from __future__ import annotations

import os
import logging
import socket
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

import uvicorn

from sdk.client import ChromiumClient


class RemoteBoundaryTest(unittest.TestCase):
    def test_client_uses_server_for_environment_runtime_and_extension(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            os.environ["QIYUAN_STARTUP_MODE"] = "server"
            os.environ["CHROMIUM_SDK_DATA_DIR"] = os.path.join(root, "server")
            os.environ["CHROMIUM_SDK_QIYUAN_DIR"] = os.path.join(root, "server-browser")
            from admin import server

            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            runner = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="error"))
            thread = threading.Thread(target=runner.run, daemon=True)
            thread.start()
            try:
                for _ in range(100):
                    if runner.started:
                        break
                    time.sleep(0.05)
                self.assertTrue(runner.started)
                client_root = os.path.join(root, "client")
                local = ChromiumClient(data_dir=client_root, remote_api_path=f"http://127.0.0.1:{port}")
                local.set_browser_app_data_dir(client_root)
                try:
                    code = server.server_client.env_create(name="remote-test")["code"]
                    environment = local._require_env(code)
                    self.assertEqual(environment["name"], "remote-test")
                    self.assertEqual(local.storage.get_token(), server.server_client.token)
                    local.storage.set_runtime(code, 12345, None)
                    self.assertEqual(server.server_client.storage.get_environment(code)["pid"], 12345)
                    proxy_code = server.server_client.proxy_create(
                        proxy_name="remote-proxy", proxy_type="http",
                        proxy_addr="127.0.0.1", proxy_port=8888,
                    )["code"]
                    self.assertEqual(local.proxy_detail(proxy_code)["proxy_name"], "remote-proxy")
                    error_code = server.server_client.report_error("remote error")["code"]
                    self.assertEqual(local.browser_error_data(error_code)["title"], "remote error")

                    archive = os.path.join(root, "extension.zip")
                    with zipfile.ZipFile(archive, "w") as target:
                        target.writestr("manifest.json", '{"manifest_version":3,"name":"Demo","version":"1.0"}')
                    with open(archive, "rb") as source:
                        server.server_client.extension_create({"code": "demo", "name": "Demo", "version": "1.0", "browser_kernel": "chrome", "environment_codes": [code]}, SimpleNamespace(file=source, filename="extension.zip"))
                    result = local.extensions.sync(environment)
                    self.assertEqual(result[0]["status"], "success")
                    self.assertTrue(Path(client_root, "user_data", code, "Default", "custom_extensions", "demo", "manifest.json").is_file())
                    self.assertFalse(Path(client_root, "db", "qiyuan.db").exists())
                finally:
                    local.close()
            finally:
                runner.should_exit = True
                thread.join(timeout=10)
                server.server_client.close()
                for logger_name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
                    logger = logging.getLogger(logger_name)
                    for handler in logger.handlers[:]:
                        logger.removeHandler(handler)
                        handler.close()


if __name__ == "__main__":
    unittest.main()
