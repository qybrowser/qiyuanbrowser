"""Client-side storage facade. All shared records live on the server."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .errors import SdkError


class RemoteStorage:
    def __init__(self, base_url: str, data_dir: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.config_file = os.path.join(data_dir, "local-client.json")

    def request(self, path: str, *, params: Optional[Dict[str, Any]] = None,
                body: Optional[Dict[str, Any]] = None) -> Any:
        url = self.base_url + path
        if params:
            url += "?" + urlencode(params)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response)
        except Exception as exc:
            raise SdkError(f"服务端不可用: {url}: {exc}") from exc
        if not result.get("success"):
            raise SdkError(str(result.get("error") or "服务端请求失败"))
        return result.get("data")

    def _local_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_file, encoding="utf-8") as source:
                data = json.load(source)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def get_config(self, key: str) -> Optional[str]:
        return self._local_config().get(key)

    def set_config(self, key: str, value: str) -> None:
        data = self._local_config()
        data[key] = value
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as target:
            json.dump(data, target, ensure_ascii=False, indent=2)

    def get_environment(self, code: str) -> Optional[Dict[str, Any]]:
        return self.request("/internal/client/environment", params={"code": code})

    def list_environments(self, page: int = 1, page_size: int = 1000000, keyword: str = ""):
        result = self.request("/internal/client/environments", params={"page": page, "page_size": page_size, "keyword": keyword}) or {}
        return result.get("items", []), int(result.get("total", 0))

    def update_environment(self, code: str, fields: Dict[str, Any]) -> bool:
        return bool(self.request("/internal/client/environment/update", body={"code": code, "fields": fields}))

    def get_proxy(self, code: str) -> Optional[Dict[str, Any]]:
        return self.request("/internal/client/proxy", params={"code": code})

    def get_error(self, code: str) -> Optional[Dict[str, Any]]:
        return self.request("/internal/client/error", params={"code": code})

    def update_proxy(self, code: str, fields: Dict[str, Any]) -> bool:
        return bool(self.request("/internal/client/proxy/update", body={"code": code, "fields": fields}))

    def set_runtime(self, code: str, pid: Optional[int], debug_port: Optional[int]) -> None:
        self.request("/internal/client/runtime", body={"code": code, "pid": pid, "debug_port": debug_port})

    def list_environment_extensions(self, code: str):
        return self.request("/internal/client/extensions", params={"code": code})

    def upsert_extension_sync(self, environment_code: str, extension_code: str, fields: Dict[str, Any]) -> None:
        self.request("/internal/client/extensions/sync-state", body={"environment_code": environment_code, "extension_code": extension_code, "fields": fields})

    def get_token(self) -> str:
        return str(self.request("/internal/client/token"))

    def close(self) -> None:
        pass
