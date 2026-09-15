"""Fingerprint generation.

Pure-compute port of the logic that lives in the Electron client
(``front-electron/src/main/http-server.ts`` -> ``buildRandomFingerprint`` /
``generateUserAgent``) and the admin UI (``front-ui/src/views/browser/index.vue``).
No network access is required.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from .system_fonts import generate_random_font_list
from .gpu_fingerprint import random_gpu

# Fallback when the caller does not pin a version. Mirrors the Electron client.
DEFAULT_CHROME_VERSION = "150.0.7871.115"

SUPPORTED_PLATFORMS = ("Win32", "MacIntel", "Linux x86_64")


def generate_user_agent(platform: str, version: str) -> str:
    """Build a User-Agent string from platform + full version number."""
    major = (version or DEFAULT_CHROME_VERSION).split(".")[0]
    chrome = f"{major}.0.0.0"
    if platform == "MacIntel":
        return (f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{chrome} Safari/537.36")
    if platform == "Linux x86_64":
        return (f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{chrome} Safari/537.36")
    # Win32 + default fallback
    return (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{chrome} Safari/537.36")


# --- offset helpers (identical ranges to the TS/Vue implementation) ----------

def _random_font() -> int:
    return random.randint(-2, 2)


def _random_canvas() -> float:
    return round(random.random(), 2)


def _random_audio() -> int:
    return random.randint(0, 99)


def _random_client_rects() -> float:
    return round(random.random() * 0.00001, 6)


def _random_media_devices() -> List[str]:
    return ["".join(random.choice("0123456789abcdef") for _ in range(64)) for _ in range(5)]


def generate_fingerprint(platform: str = "Win32") -> Dict[str, object]:
    """Generate a complete random fingerprint for ``platform``.

    Returns a dict that is both human-readable (split vendor/renderer fields)
    and ready to persist alongside an environment.
    """
    if platform not in SUPPORTED_PLATFORMS:
        platform = "Win32"

    vendor, renderer, gpu_v, gpu_a, gpu_d, gpu_desc = random_gpu(platform)
    webgl_value = f"{vendor}|{renderer}"
    webgpu_value = f"{gpu_v}|{gpu_a}|{gpu_d}|{gpu_desc}"

    return {
        "platform": platform,
        "webrtc": "ip",
        "webgl_type": "custom",
        "webgl_value": webgl_value,
        "webgl_vendor": vendor,
        "webgl_renderer": renderer,
        "webgpu_type": "custom",
        "webgpu_value": webgpu_value,
        "timezone_type": "ip",
        "geo_location_type": "ip",
        "language_type": "ip",
        "ui_language_type": "language",
        "screen_resolution_type": "real",
        "font": _random_font(),
        "canvas": _random_canvas(),
        "audio": _random_audio(),
        "client_rects": _random_client_rects(),
        "speech_voices": random.random() > 0.5,
        "media_devices": _random_media_devices(),
        "font_list": generate_random_font_list(),
        "local_port_access": "all",  # 默认关闭端口扫描保护
        "do_not_track": 1,
        "tls_type": "enabled",
        "tls_value": ":!aPSK,:!kRSA,:!ECDSA,:!ECDSA+SHA1,:!3DES",
    }


_DEFAULT_TLS_FEATURES = [":!aPSK", ":!kRSA", ":!ECDSA", ":!ECDSA+SHA1", ":!3DES"]


def build_fingerprint_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a form-style payload into flat storage fields.

    Port of ``http-server.ts::buildFingerprintPayload`` — only keys present in
    ``data`` produce output, so it can be overlaid onto a base fingerprint.
    """
    out: Dict[str, Any] = {}

    if "webrtc" in data:
        out["webrtc"] = data.get("webrtc") or "disabled"

    if "webgl" in data:
        out["webgl_type"] = data["webgl"]
        if data["webgl"] == "custom":
            vendor = data.get("webgl_vendor") or ""
            renderer = data.get("webgl_renderer") or ""
            out["webgl_value"] = f"{vendor}|{renderer}" if vendor and renderer else ""

    if "webgpu" in data:
        out["webgpu_type"] = data["webgpu"]
        if data["webgpu"] == "custom":
            v = data.get("webgpu_vendor") or ""
            a = data.get("webgpu_architecture") or ""
            d = data.get("webgpu_device") or ""
            s = data.get("webgpu_description") or ""
            out["webgpu_value"] = f"{v}|{a}|{d}|{s}"

    if "timezone" in data:
        out["timezone_type"] = data["timezone"]
        if data["timezone"] == "custom" and data.get("timezone_value") is not None:
            out["timezone_value"] = data["timezone_value"]

    if "geo_location" in data:
        out["geo_location_type"] = data["geo_location"]
        if data["geo_location"] == "custom":
            lng = data.get("longitude") or ""
            lat = data.get("latitude") or ""
            out["geo_location_value"] = f"{lng}|{lat}" if lng and lat else ""

    if "language" in data:
        out["language_type"] = data["language"]
        if data["language"] == "custom" and isinstance(data.get("languages"), list):
            out["language_value"] = ",".join(data["languages"])

    if "ui_language" in data:
        out["ui_language_type"] = data["ui_language"]
        if data["ui_language"] == "custom" and data.get("ui_language_value") is not None:
            out["ui_language_value"] = data["ui_language_value"]

    if "screen_resolution" in data:
        out["screen_resolution_type"] = data["screen_resolution"]
        if data["screen_resolution"] == "custom" and data.get("screen_resolution_value") is not None:
            out["screen_resolution_value"] = data["screen_resolution_value"]

    if "font" in data:
        out["font"] = 0 if data["font"] == "disabled" else _random_font()
    if "canvas" in data:
        out["canvas"] = 0 if data["canvas"] == "disabled" else _random_canvas()
    if "audio" in data:
        out["audio"] = 0 if data["audio"] == "disabled" else _random_audio()
    if "client_rects" in data:
        out["client_rects"] = 0 if data["client_rects"] == "disabled" else _random_client_rects()

    if "speech_voices" in data:
        out["speech_voices"] = data["speech_voices"]

    if "media_devices" in data:
        out["media_devices"] = None if data["media_devices"] == "disabled" else _random_media_devices()

    if "font_list" in data:
        mode = data["font_list"]
        if mode in ("disabled", None) or mode is False:
            out["font_list"] = None
        elif isinstance(mode, list):
            out["font_list"] = mode or None
        else:
            # "random" or any other truthy mode → enumerate + randomize
            out["font_list"] = generate_random_font_list()

    if "local_port_access" in data:
        raw = data.get("local_port_access")
        text = str(raw if raw is not None else "all").strip().lower() or "all"
        out["local_port_access"] = text

    if "do_not_track" in data:
        dnt = data["do_not_track"]
        if dnt in (True, 1, "1", "true"):
            out["do_not_track"] = 1
        elif dnt in (False, 0, "0", "false"):
            out["do_not_track"] = 0
        else:
            out["do_not_track"] = 1

    hw: Dict[str, str] = {}
    if data.get("cpu_cores") not in (None, "", "real"):
        hw["cpu_cores"] = data["cpu_cores"]
    if data.get("memory_gb") not in (None, "", "real"):
        hw["memory_gb"] = data["memory_gb"]
    if hw:
        out["hardware_info"] = hw

    if "tls" in data:
        out["tls_type"] = data["tls"]
        if data["tls"] == "enabled":
            features = data.get("tls_features")
            if not isinstance(features, list):
                features = list(_DEFAULT_TLS_FEATURES)
            out["tls_value"] = ",".join(features)

    return out


_DEFAULT_HARDWARE = {"color_depth": "24", "cpu_cores": "8", "memory_gb": "8"}


def build_fingerprint_json(
    env: Dict[str, Any],
    fp: Dict[str, Any],
    proxy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Transform a stored (flat) fingerprint + environment + proxy into the
    nested JSON the client browser expects.

    Mirrors ``backend/app/api/v1/browser.py::get_browser_by_md5`` so the qiyuan
    chrome can consume it after AES decryption.
    """
    fp = fp or {}
    payload = {
        "audio": str(fp["audio"]) if fp.get("audio") else "",
        "canvas": str(fp["canvas"]) if fp.get("canvas") else "",
        "client_rects": f"{float(fp['client_rects']):.6f}" if fp.get("client_rects") else "",
        "font": str(fp["font"]) if fp.get("font") else "",
        "geo_location": {"type": fp.get("geo_location_type", "ip"), "value": fp.get("geo_location_value")},
        "hardware_info": fp.get("hardware_info") or dict(_DEFAULT_HARDWARE),
        "tls": {"type": fp.get("tls_type", "enabled"), "value": fp.get("tls_value")},
        "language": {"type": fp.get("language_type", "ip"), "value": fp.get("language_value")},
        "platform": fp.get("platform") or env.get("platform"),
        "screen_resolution": {"type": fp.get("screen_resolution_type", "real"), "value": fp.get("screen_resolution_value")},
        "timestamp": datetime.now().isoformat() + "Z",
        "timezone": {"type": fp.get("timezone_type", "ip"), "value": fp.get("timezone_value")},
        "ui_language": {"type": fp.get("ui_language_type", "language"), "value": fp.get("ui_language_value")},
        "user_agent": env.get("user_agent"),
        "browser_version": env.get("browser_version"),
        "webgl": {"type": fp.get("webgl_type"), "value": fp.get("webgl_value")},
        "webgpu": {"type": fp.get("webgpu_type"), "value": fp.get("webgpu_value")},
        "webrtc": fp.get("webrtc") or "",
        "speech_voices": fp.get("speech_voices") or False,
        "media_devices": fp.get("media_devices") or [],
        "font_list": fp.get("font_list") or [],
        "local_port_access": fp.get("local_port_access") or "all",
        "do_not_track": 1 if fp.get("do_not_track", 1) else 0,
        "open_home_page": bool(env.get("open_home_page")),
        "enable_tabs": bool(env.get("enable_tabs")),
        "tabs": env.get("tabs") if env.get("tabs") and env.get("enable_tabs") else "",
        "sync_user_info": bool(env.get("sync_user_info")),
        "cookie": env.get("cookie") or "",
        "launch_args": env.get("launch_args") or "",
        # 任务栏角标：SDK 固定取名称前 3 字（对齐 backend mode=name）
        "taskbar_badge": ((env.get("name") or "").strip()[:3]),
    }

    if proxy:
        proxy_info: Dict[str, Any] = {
            "proxy_type": proxy.get("proxy_type"),
            "proxy_addr": proxy.get("proxy_addr"),
        }
        if proxy.get("proxy_port") is not None:
            proxy_info["proxy_port"] = str(proxy["proxy_port"])
        if proxy.get("username"):
            proxy_info["username"] = proxy["username"]
        if proxy.get("password"):
            proxy_info["password"] = proxy["password"]
        payload["proxy_info"] = proxy_info

    return payload
