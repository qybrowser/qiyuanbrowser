"""Standalone Qiyuan SDK client process.

The client owns local browser control and exposes the local management UI/API.
Shared environments, proxies and extensions are always accessed through the
server configured by ``base_api_path``.
"""

from __future__ import annotations

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ["QIYUAN_PROCESS_ROLE"] = "client"

# Resolve the config before importing admin.server (and therefore sdk config).
# PyInstaller bootstrapping can otherwise make the later parser see a different
# argv view and fall back to the source-tree default path.
_config_arg = None
for _index, _arg in enumerate(sys.argv):
    if _arg == "--config" and _index + 1 < len(sys.argv):
        _config_arg = sys.argv[_index + 1]
        break
    if _arg.startswith("--config="):
        _config_arg = _arg.split("=", 1)[1]
        break
if _config_arg:
    os.environ["QIYUAN_CONFIG_PATH"] = os.path.abspath(os.path.expandvars(os.path.expanduser(_config_arg)))
else:
    default_config = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "browser-config-client.json"))
    if os.path.isfile(default_config):
        os.environ["QIYUAN_CONFIG_PATH"] = default_config

from admin.server import app, _local_listener_port


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=_local_listener_port(),
        loop="admin.event_loop:selector_loop_factory",
    )
