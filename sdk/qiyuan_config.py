"""Browser paths and the three independent endpoint URLs in config.json."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import sys
import tempfile
import zipfile
from typing import Any, Dict, Optional

_CONFIG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_KERNEL_CONFIG_PATH = os.path.join(
    _CONFIG_ROOT,
    "browser-config-client.json" if os.environ.get("QIYUAN_PROCESS_ROLE", "server").lower() == "client" else "browser-config-server.json",
)


def kernel_config_path() -> str:
    configured = os.environ.get("QIYUAN_CONFIG_PATH")
    if configured:
        return os.path.abspath(os.path.expandvars(os.path.expanduser(configured)))
    # A frozen client keeps its editable configuration beside the executable;
    # source launches continue to use the repository-level file.
    if getattr(sys, "frozen", False):
        executable_name = "browser-config-client.json" if os.environ.get("QIYUAN_PROCESS_ROLE", "server").lower() == "client" else "browser-config-server.json"
        executable_config = os.path.join(os.path.dirname(sys.executable), executable_name)
        if os.path.isfile(executable_config):
            return os.path.abspath(executable_config)
    return DEFAULT_KERNEL_CONFIG_PATH


def kernel_catalog() -> Dict[str, Dict[str, Any]]:
    """Return the shipped versions; filesystem contents never decide public defaults."""
    with open(kernel_config_path(), encoding="utf-8") as source:
        data = json.load(source)
    kernels = data.get("kernels")
    if not isinstance(kernels, dict) or set(kernels) != {"chrome", "firefox"}:
        raise ValueError("browser configuration must define chrome and firefox")
    for kernel, spec in kernels.items():
        versions = spec.get("versions") if isinstance(spec, dict) else None
        default = spec.get("default_version") if isinstance(spec, dict) else None
        if not isinstance(versions, list) or not versions or not all(
            isinstance(version, str) and version and version not in (".", "..")
            and "/" not in version and "\\" not in version for version in versions
        ) or default not in versions:
            raise ValueError(f"Invalid {kernel} versions in browser configuration")
    return kernels


def kernel_installed(version: str, kernel: str, root: str) -> bool:
    directory = os.path.join(root, "client", version)
    markers = ("application.ini", "platform.ini") if kernel == "firefox" else ("chrome.dll",)
    executable = browser_executable(version, kernel, root)
    return os.path.isfile(executable) and any(
        os.path.isfile(os.path.join(directory, marker)) for marker in markers
    )


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


def browser_executable(browser_version: str, kernel: str = "chrome", browser_app_data_dir: Optional[str] = None) -> str:
    version_dir = os.path.join(client_dir(browser_app_data_dir), browser_version)
    if sys.platform == "win32":
        names = ("QyBrowser.exe", "firefox.exe") if kernel == "firefox" else ("QyBrowser.exe", "chrome.exe")
        for name in names:
            candidate = os.path.join(version_dir, name)
            if os.path.exists(candidate):
                return candidate
        return os.path.join(version_dir, "QyBrowser.exe")
    return os.path.join(version_dir, "firefox" if kernel == "firefox" else "chrome")


def chrome_executable(browser_version: str, browser_app_data_dir: Optional[str] = None) -> str:
    """Backward-compatible Chromium executable lookup."""
    return browser_executable(browser_version, "chrome", browser_app_data_dir)


def default_browser_version(kernel: str, browser_app_data_dir: Optional[str] = None) -> Optional[str]:
    spec = kernel_catalog().get(kernel)
    return spec["default_version"] if spec else None


def inspect_qiyuan_dir(browser_app_data_dir: Optional[str] = None) -> Dict[str, Any]:
    root = qiyuan_dir(browser_app_data_dir)
    client = os.path.join(root, "client")
    kernels = {
        name: {
            "default_version": spec["default_version"],
            "versions": list(spec["versions"]),
            "installed_versions": [version for version in spec["versions"] if kernel_installed(version, name, root)],
        }
        for name, spec in kernel_catalog().items()
    }
    versions = sorted({version for spec in kernels.values() for version in spec["installed_versions"]})
    missing = [f"{name}/{version}" for name, spec in kernels.items()
               for version in spec["versions"] if version not in spec["installed_versions"]]
    checks = {
        "root": os.path.isdir(root),
        "client": os.path.isdir(client),
        "config": os.path.isfile(os.path.join(root, "config", "config.json")),
        "extends": os.path.isdir(os.path.join(root, "extends")),
        "executable": not missing,
    }
    return {
        "browser_app_data_dir": root,
        "is_default": os.path.normcase(root) == os.path.normcase(default_qiyuan_dir()),
        "valid": all(checks.values()),
        "checks": checks,
        "browser_versions": versions,
        "kernels": kernels,
        "missing_versions": missing,
    }


def bundled_browser_config() -> Dict[str, Any]:
    with open(kernel_config_path(), "r", encoding="utf-8") as source:
        return json.load(source)


def configured_token() -> str:
    return str(bundled_browser_config().get("api_token") or "")


def set_configured_token(token: str) -> None:
    path = kernel_config_path()
    data = bundled_browser_config()
    data["api_token"] = token
    with open(path, "w", encoding="utf-8") as target:
        json.dump(data, target, ensure_ascii=False, indent=2)


def update_kernel_config(kernel: str, version: str, set_default: bool = False) -> Dict[str, Any]:
    if kernel not in ("chrome", "firefox") or not version or version in (".", "..") or "/" in version or "\\" in version:
        raise ValueError("无效的内核或版本号")
    path = kernel_config_path()
    data = bundled_browser_config()
    spec = data.setdefault("kernels", {}).setdefault(kernel, {"default_version": version, "versions": []})
    versions = list(spec.get("versions") or [])
    if version not in versions:
        versions.append(version)
    spec["versions"] = versions
    if set_default or not spec.get("default_version"):
        spec["default_version"] = version
    with open(path, "w", encoding="utf-8") as target:
        json.dump(data, target, ensure_ascii=False, indent=2)
    return data


def install_kernel_archive(browser_app_data_dir: str, kernel: str, version: str, uploaded: Any, set_default: bool = False) -> Dict[str, Any]:
    """Safely install a user-uploaded kernel ZIP into the client app-data directory."""
    if kernel not in ("chrome", "firefox") or not version or version in (".", "..") or "/" in version or "\\" in version:
        raise ValueError("无效的内核或版本号")
    root = qiyuan_dir(browser_app_data_dir)
    os.makedirs(client_dir(root), exist_ok=True)
    temporary_root = tempfile.mkdtemp(prefix="kernel-", dir=root)
    archive_path = os.path.join(temporary_root, "kernel.zip")
    extract_root = os.path.join(temporary_root, "extract")
    try:
        uploaded.file.seek(0)
        with open(archive_path, "wb") as target:
            shutil.copyfileobj(uploaded.file, target)
        os.makedirs(extract_root, exist_ok=True)
        with zipfile.ZipFile(archive_path) as archive:
            base = os.path.abspath(extract_root)
            for member in archive.infolist():
                target = os.path.abspath(os.path.join(extract_root, member.filename))
                if not target.startswith(base + os.sep):
                    raise ValueError("内核 ZIP 包含非法路径")
            archive.extractall(extract_root)
        entries = [name for name in os.listdir(extract_root) if name not in ("__MACOSX",)]
        source_root = extract_root
        if len(entries) == 1 and os.path.isdir(os.path.join(extract_root, entries[0])):
            source_root = os.path.join(extract_root, entries[0])
        destination = os.path.join(client_dir(root), version)
        staging = destination + ".uploading"
        if os.path.isdir(staging):
            shutil.rmtree(staging)
        shutil.copytree(source_root, staging)
        executable_names = ("QyBrowser.exe", "firefox.exe") if kernel == "firefox" else ("QyBrowser.exe", "chrome.exe")
        markers = ("application.ini", "platform.ini") if kernel == "firefox" else ("chrome.dll",)
        valid_executable = any(os.path.isfile(os.path.join(staging, name)) for name in executable_names)
        valid_markers = any(os.path.isfile(os.path.join(staging, name)) for name in markers)
        if not valid_executable or not valid_markers:
            shutil.rmtree(staging, ignore_errors=True)
            raise ValueError(f"内核文件校验失败，请确认上传的是 {kernel} 内核")
        if os.path.isdir(destination):
            shutil.rmtree(destination)
        os.replace(staging, destination)
        update_kernel_config(kernel, version, set_default)
        return inspect_qiyuan_dir(root)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def client_runtime_config() -> Dict[str, Any]:
    """Return the URL/runtime section generated into the app-data config.json."""
    data = bundled_browser_config()
    result = {key: data[key] for key in ("base_api_path", "base_local_api_path") if data.get(key)}
    if result.get("base_api_path"):
        result["browser_base_path"] = result["base_api_path"]
    return result


def ensure_qiyuan_config(
    local_api_path: Optional[str] = None,
    browser_base_path: Optional[str] = None,
    browser_app_data_dir: Optional[str] = None,
) -> str:
    """Synchronize URLs without conflating server, local API, and page hosts.

    The bundled config is authoritative for the default browser directory.
    A custom browser directory owns its own config; only explicit overrides
    replace those URLs. Other config keys are preserved.
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

    default_root = os.path.normcase(qiyuan_dir(browser_app_data_dir)) == os.path.normcase(default_qiyuan_dir())
    source = bundled_browser_config() if default_root else data or bundled_browser_config()
    expected = {
        "base_api_path": source.get("base_api_path"),
        "base_local_api_path": local_api_path or source.get("base_local_api_path"),
        "browser_base_path": browser_base_path or source.get("browser_base_path") or source.get("base_api_path"),
    }
    changed = not os.path.exists(path)
    for key, value in expected.items():
        if value and data.get(key) != value:
            data[key] = value
            changed = True
    # Fingerprint settings are stored per environment, never in the browser
    # bootstrap configuration.
    if "fingerprint" in data:
        data.pop("fingerprint", None)
        changed = True

    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    return path
