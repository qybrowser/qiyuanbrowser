"""Typed dataclasses describing the records the SDK works with.

These are lightweight conveniences; the SDK itself passes plain dicts so that
the HTTP layer can serialise them directly. Use :meth:`from_dict` to wrap a
record returned by :class:`sdk.client.ChromiumClient`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Fingerprint:
    platform: str = "Win32"
    webgl_value: str = ""
    webgpu_value: str = ""
    font: int = 0
    canvas: float = 0.0
    audio: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fingerprint":
        known = {"platform", "webgl_value", "webgpu_value", "font", "canvas", "audio"}
        return cls(
            platform=data.get("platform", "Win32"),
            webgl_value=data.get("webgl_value", ""),
            webgpu_value=data.get("webgpu_value", ""),
            font=data.get("font", 0),
            canvas=data.get("canvas", 0.0),
            audio=data.get("audio", 0),
            extra={k: v for k, v in data.items() if k not in known},
        )


@dataclass
class Environment:
    code: str
    name: str
    platform: str = "Win32"
    browser_version: Optional[str] = None
    user_agent: Optional[str] = None
    proxy_code: Optional[str] = None
    status: str = "stopped"
    debug_port: Optional[int] = None
    remark: str = ""
    tag_ids: List[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Environment":
        return cls(
            code=data["code"],
            name=data["name"],
            platform=data.get("platform", "Win32"),
            browser_version=data.get("browser_version"),
            user_agent=data.get("user_agent"),
            proxy_code=data.get("proxy_code"),
            status=data.get("status", "stopped"),
            debug_port=data.get("debug_port"),
            remark=data.get("remark", ""),
            tag_ids=data.get("tag_ids", []) or [],
        )


@dataclass
class Proxy:
    code: str
    proxy_name: str
    proxy_type: str
    proxy_addr: str
    proxy_port: int
    username: str = ""
    password: str = ""
    remark: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Proxy":
        return cls(
            code=data["code"],
            proxy_name=data["proxy_name"],
            proxy_type=data["proxy_type"],
            proxy_addr=data["proxy_addr"],
            proxy_port=int(data["proxy_port"]),
            username=data.get("username", ""),
            password=data.get("password", ""),
            remark=data.get("remark", ""),
        )
