"""qiyuan client paths and config.json integration.

The launched client browser learns which server to call back into from
``~/.qiyuan/config/config.json`` (the ``base_api_path`` field). For the
self-contained SDK to be that server, we merge our admin server URL into it
before opening a browser.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional


def get_appdata() -> str:
    """Resolve the platform AppData/Roaming-equivalent directory.

    Override with ``CHROMIUM_SDK_APPDATA`` (useful on non-Windows / for tests).
    """
    override = os.environ.get("CHROMIUM_SDK_APPDATA")
    if override:
        return override
    if sys.platform == "win32":
        return os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    return os.path.expanduser("~/.config")


def default_qiyuan_dir() -> str:
    return os.path.abspath(os.path.join(os.path.expanduser("~"), ".qiyuan"))


def qiyuan_dir(browser_app_data_dir: Optional[str] = None) -> str:
    value = browser_app_data_dir or os.environ.get("CHROMIUM_SDK_QIYUAN_DIR")
    return os.path.abspath(os.path.expandvars(os.path.expanduser(value))) if value else default_qiyuan_dir()


def client_dir(browser_app_data_dir: Optional[str] = None) -> str:
    return os.path.join(qiyuan_dir(browser_app_data_dir), "client")


def user_data_root(browser_app_data_dir: Optional[str] = None) -> str:
    return os.path.join(qiyuan_dir(browser_app_data_dir), "user_data")


def config_path(browser_app_data_dir: Optional[str] = None) -> str:
    return os.path.join(qiyuan_dir(browser_app_data_dir), "config", "config.json")


def chrome_executable(browser_version: str, browser_app_data_dir: Optional[str] = None) -> str:
    version_dir = os.path.join(client_dir(browser_app_data_dir), browser_version)
    if sys.platform == "win32":
        for name in ("QyBrowser.exe", "chrome.exe"):
            candidate = os.path.join(version_dir, name)
            if os.path.exists(candidate):
                return candidate
        return os.path.join(version_dir, "QyBrowser.exe")
    return os.path.join(version_dir, "chrome")


def inspect_qiyuan_dir(browser_app_data_dir: Optional[str] = None) -> Dict[str, Any]:
    root = qiyuan_dir(browser_app_data_dir)
    client = os.path.join(root, "client")
    versions = []
    if os.path.isdir(client):
        for name in sorted(os.listdir(client)):
            if os.path.isfile(chrome_executable(name, root)):
                versions.append(name)
    checks = {
        "root": os.path.isdir(root),
        "client": os.path.isdir(client),
        "config": os.path.isfile(os.path.join(root, "config", "config.json")),
        "extends": os.path.isdir(os.path.join(root, "extends")),
        "executable": bool(versions),
    }
    return {
        "browser_app_data_dir": root,
        "is_default": os.path.normcase(root) == os.path.normcase(default_qiyuan_dir()),
        "valid": all(checks.values()),
        "checks": checks,
        "browser_versions": versions,
    }


def ensure_qiyuan_config(
    base_api_path: str,
    browser_base_path: Optional[str] = None,
    browser_app_data_dir: Optional[str] = None,
) -> str:
    """Ensure config.json has the server URLs the client browser needs.

    - ``base_api_path`` / ``base_local_api_path``: where the browser calls the
      API (md5 / status / check-proxy / ...); both default to base_api_path.
    - ``browser_base_path``: where the browser loads the start / error pages
      (``{browser_base_path}/pages/home.html`` etc.); defaults to base_api_path.

    The three server URLs are synchronized so an old SDK port cannot remain in
    a previously copied config. Other keys are preserved.
    """
    path = config_path(browser_app_data_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data: dict = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
        except (ValueError, OSError):
            data = {}

    expected = {
        "base_api_path": base_api_path,
        "base_local_api_path": base_api_path,
        "browser_base_path": browser_base_path or base_api_path,
    }
    changed = not os.path.exists(path)
    for key, value in expected.items():
        if data.get(key) != value:
            data[key] = value
            changed = True

    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    return path
