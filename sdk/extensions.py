"""Extension storage, validation, and per-environment synchronization."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from urllib.request import urlopen
from pathlib import Path
from typing import Any, Dict, Iterable, List

from . import qiyuan_config
from .errors import NotFoundError, ValidationError


def _safe_code(value: str) -> str:
    value = (value or "").strip()
    if not value or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in value):
        raise ValidationError("扩展 code 只能包含字母、数字、下划线和短横线")
    return value


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _config() -> Dict[str, Any]:
    return qiyuan_config.bundled_browser_config().get("extensions", {})


class ExtensionManager:
    def __init__(self, storage: Any, browser_app_data_dir: str, remote_api_path: str | None = None) -> None:
        self.storage = storage
        self.browser_app_data_dir = browser_app_data_dir
        self.remote_api_path = remote_api_path

    @property
    def cache_dir(self) -> str:
        configured = str(_config().get("cache_dir") or "extension-cache")
        return os.path.join(self.browser_app_data_dir, configured)

    def _source_zip(self, extension: Dict[str, Any]) -> str:
        if self.remote_api_path:
            cached = os.path.join(self.cache_dir, extension["code"], f"{extension['version']}.zip")
            if os.path.isfile(cached) and _sha256(cached) == extension.get("sha256"):
                return cached
            os.makedirs(os.path.dirname(cached), exist_ok=True)
            source_url = f"{self.remote_api_path}/internal/client/extensions/download/{extension['code']}"
            temporary = cached + ".downloading"
            try:
                with urlopen(source_url, timeout=60) as source, open(temporary, "wb") as output:
                    shutil.copyfileobj(source, output)
                self.validate_zip(temporary)
                if _sha256(temporary) != extension.get("sha256"):
                    raise ValidationError(f"扩展校验失败: {extension['code']}")
                os.replace(temporary, cached)
            finally:
                if os.path.exists(temporary): os.remove(temporary)
            return cached
        path = extension.get("file_path") or ""
        if path and os.path.isfile(path):
            return path
        cached = os.path.join(self.cache_dir, extension["code"], f"{extension['version']}.zip")
        if os.path.isfile(cached):
            return cached
        raise ValidationError(f"扩展文件不存在: {extension['code']}")

    def validate_zip(self, path: str) -> None:
        if not path or not os.path.isfile(path):
            raise ValidationError("扩展文件必须是 ZIP")
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                if not any(name.rstrip("/").split("/")[-1] == "manifest.json" for name in names):
                    raise ValidationError("扩展 ZIP 缺少 manifest.json")
                for name in names:
                    target = Path(name)
                    if target.is_absolute() or ".." in target.parts:
                        raise ValidationError("扩展 ZIP 包含非法路径")
        except zipfile.BadZipFile as exc:
            raise ValidationError("扩展文件不是有效 ZIP") from exc

    def save_upload(self, code: str, version: str, uploaded: Any) -> Dict[str, Any]:
        code = _safe_code(code)
        if not version.strip():
            raise ValidationError("扩展版本不能为空")
        os.makedirs(os.path.join(self.cache_dir, code), exist_ok=True)
        destination = os.path.join(self.cache_dir, code, f"{version.strip()}.zip")
        uploaded.file.seek(0)
        with open(destination, "wb") as target:
            shutil.copyfileobj(uploaded.file, target)
        self.validate_zip(destination)
        result = {"file_path": destination, "file_name": uploaded.filename or f"{code}.zip", "sha256": _sha256(destination), "file_size": os.path.getsize(destination)}
        if str(_config().get("storage", "local")).lower() == "oss":
            result["oss_key"] = self._oss_upload(code, version, destination)
        return result

    def _oss_upload(self, code: str, version: str, path: str) -> str:
        settings = _config().get("oss") or {}
        endpoint, bucket_name = settings.get("endpoint"), settings.get("bucket")
        if not endpoint or not bucket_name:
            raise ValidationError("已启用 OSS，但未配置 endpoint/bucket")
        try:
            import oss2  # type: ignore
        except ImportError as exc:
            raise ValidationError("OSS 存储需要安装 oss2") from exc
        access = os.environ.get(settings.get("access_key_env", "QIYUAN_OSS_ACCESS_KEY"), "")
        secret = os.environ.get(settings.get("secret_key_env", "QIYUAN_OSS_SECRET_KEY"), "")
        if not access or not secret:
            raise ValidationError("OSS 凭据环境变量未配置")
        key = "/".join(x.strip("/") for x in (settings.get("prefix", ""), code, f"{version}.zip") if x)
        oss2.Bucket(oss2.Auth(access, secret), endpoint, bucket_name).put_object_from_file(key, path)
        return key

    def list(self, page: int = 1, page_size: int = 20, keyword: str = "", kernel: str = "", extension_type: str = "") -> Dict[str, Any]:
        items, total = self.storage.list_extensions(page, page_size, keyword, kernel, extension_type)
        for item in items:
            item["environment_codes"] = self.storage.get_extension_bindings(item["code"])
        return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}

    def detail(self, code: str) -> Dict[str, Any]:
        item = self.storage.get_extension(code)
        if not item: raise NotFoundError("扩展不存在")
        item["environment_codes"] = self.storage.get_extension_bindings(code)
        return item

    def create(self, data: Dict[str, Any], uploaded: Any = None) -> Dict[str, Any]:
        code = _safe_code(str(data.get("code") or ""))
        kernel = data.get("browser_kernel") or "chrome"
        ext_type = data.get("extension_type") or "normal"
        if kernel not in ("chrome", "firefox"): raise ValidationError("browser_kernel 必须为 chrome 或 firefox")
        if ext_type not in ("builtin", "normal"): raise ValidationError("extension_type 必须为 builtin 或 normal")
        if not data.get("name") or not data.get("version"): raise ValidationError("扩展名称和版本不能为空")
        if uploaded is None: raise ValidationError("请上传扩展 ZIP 文件")
        if self.storage.get_extension(code): raise ValidationError("扩展 code 已存在")
        file_data = self.save_upload(code, str(data["version"]), uploaded) if uploaded else {}
        item = self.storage.insert_extension({**data, "code": code, "browser_kernel": kernel, "extension_type": ext_type, **file_data})
        self.set_bindings(code, data.get("environment_codes") or (["*"] if data.get("bind_all") else []))
        return self.detail(item["code"])

    def update(self, code: str, data: Dict[str, Any], uploaded: Any = None) -> Dict[str, Any]:
        current = self.detail(code)
        changes = {key: data[key] for key in ("name", "version", "browser_kernel", "extension_type", "provider", "source_url", "description", "status") if key in data and data[key] != ""}
        if uploaded:
            version = str(data.get("version") or current["version"])
            changes.update(self.save_upload(code, version, uploaded))
        self.storage.update_extension(code, changes)
        if "environment_codes" in data or "bind_all" in data:
            self.set_bindings(code, data.get("environment_codes") or (["*"] if data.get("bind_all") else []))
        return self.detail(code)

    def set_bindings(self, code: str, environments: Iterable[str]) -> None:
        values = [str(item) for item in environments if str(item)]
        if "*" in values: values = ["*"]
        for environment in values:
            if environment != "*" and not self.storage.get_environment(environment):
                raise ValidationError(f"环境不存在: {environment}")
        self.storage.set_extension_bindings(code, values)

    def delete(self, code: str) -> Dict[str, Any]:
        item = self.detail(code)
        # Built-in copies are shared across environments and may exist even
        # when no environment is currently bound.
        if item.get("extension_type") == "builtin":
            for root in (os.path.join(self.browser_app_data_dir, "extends"), os.path.join(self.browser_app_data_dir, "client")):
                if os.path.isdir(root):
                    for path in Path(root).rglob(code):
                        if path.is_dir() and path.name == code: shutil.rmtree(path, ignore_errors=True)
        for env in self.storage.list_environments(1, 1000000, "")[0]:
            for path in self._target_paths(env, item):
                if os.path.isdir(path): shutil.rmtree(path, ignore_errors=True)
        cache = os.path.join(self.cache_dir, code)
        if os.path.isdir(cache): shutil.rmtree(cache, ignore_errors=True)
        self.storage.delete_extension(code)
        return {"code": code}

    def sync(self, environment: Dict[str, Any]) -> List[Dict[str, Any]]:
        code = environment["code"]; kernel = environment.get("browser_kernel") or "chrome"
        extensions = [ext for ext in self.storage.list_environment_extensions(code) if ext.get("browser_kernel") == kernel]
        # Remove normal extensions no longer bound to this environment.
        normal_base = self._target_base(environment, False)
        if os.path.isdir(normal_base):
            allowed_normal = {ext["code"] for ext in extensions if ext.get("extension_type") != "builtin"}
            for entry in os.listdir(normal_base):
                target = os.path.join(normal_base, entry)
                if entry not in allowed_normal and os.path.isdir(target): shutil.rmtree(target, ignore_errors=True)
        results = []
        for ext in extensions:
            for target in self._target_paths(environment, ext):
                try:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    source = self._source_zip(ext)
                    if os.path.isdir(target): shutil.rmtree(target, ignore_errors=True)
                    temp = tempfile.mkdtemp(prefix=f"{ext['code']}-", dir=os.path.dirname(target))
                    with zipfile.ZipFile(source) as archive: archive.extractall(temp)
                    manifests = list(Path(temp).rglob("manifest.json"))
                    root = str(manifests[0].parent) if manifests else temp
                    shutil.move(root, target)
                    if root != temp and os.path.isdir(temp): shutil.rmtree(temp, ignore_errors=True)
                    self.storage.upsert_extension_sync(code, ext["code"], {"version": ext["version"], "target_path": target, "sha256": ext.get("sha256", "")})
                    results.append({"code": ext["code"], "status": "success", "target_path": target})
                except Exception as exc:
                    self.storage.upsert_extension_sync(code, ext["code"], {"version": ext["version"], "target_path": target, "sha256": ext.get("sha256", ""), "sync_status": "failed", "error_message": str(exc)})
                    results.append({"code": ext["code"], "status": "failed", "error": str(exc)})
        return results

    def _target_base(self, environment: Dict[str, Any], builtin: bool) -> str:
        kernel = environment.get("browser_kernel") or "chrome"; version = environment.get("browser_version") or ""; code = environment["code"]
        if kernel == "firefox":
            return os.path.join(self.browser_app_data_dir, "client", version, "custom-extensions") if builtin else os.path.join(self.browser_app_data_dir, "user_data", code, "extensions")
        return os.path.join(self.browser_app_data_dir, "extends") if builtin else os.path.join(self.browser_app_data_dir, "user_data", code, "Default", "custom_extensions")

    def _target_paths(self, environment: Dict[str, Any], extension: Dict[str, Any]) -> List[str]:
        code, kernel = environment["code"], environment.get("browser_kernel") or "chrome"
        version = environment.get("browser_version") or ""
        builtin = extension.get("extension_type") == "builtin"
        base = self._target_base(environment, builtin)
        return [os.path.join(base, extension["code"])]
