"""ChromiumClient - the single unified facade.

Combines three surfaces into one module:

* "remote backend" operations (environment / proxy CRUD) -> reimplemented over
  a local SQLite store, so no cloud backend is required.
* "local" operations (open / close / status / clear_cache) -> drive a real
  qiyuan client-browser process on this machine.
* "server callbacks" -> the endpoints the launched browser calls back into
  (fingerprint pull, error report, tabs, status, ip-geo / check-proxy). These
  are exposed over HTTP by ``admin/server.py`` but the logic lives here.

All methods raise :class:`chromium_sdk.errors.SdkError` subclasses on failure.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
from contextlib import closing
from typing import Any, Dict, List, Optional

from . import fingerprint as fp, qiyuan_config
from .errors import NotFoundError, ValidationError
from .launcher import BrowserLauncher
from .storage import Storage

# Default URL the launched browser is told to call back into.
DEFAULT_BASE_API_PATH = "http://127.0.0.1:9003"


class ChromiumClient:
    def __init__(
        self,
        data_dir: Optional[str] = None,
        base_api_path: Optional[str] = None,
    ) -> None:
        base = data_dir or os.path.join(os.path.expanduser("~"), ".qiyuan")
        os.makedirs(base, exist_ok=True)
        self.data_dir = base
        db_path = os.path.join(base, "db", "qiyuan.db")
        legacy_db_path = os.path.join(base, "chromium_sdk.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        if not os.path.exists(db_path) and os.path.isfile(legacy_db_path):
            # SQLite backup also includes committed WAL data; leave the old DB intact.
            temporary_db_path = db_path + ".migrating"
            try:
                with closing(sqlite3.connect(legacy_db_path)) as source:
                    with closing(sqlite3.connect(temporary_db_path)) as destination:
                        source.backup(destination)
                os.replace(temporary_db_path, db_path)
            finally:
                if os.path.exists(temporary_db_path):
                    os.remove(temporary_db_path)
        self.storage = Storage(db_path)
        configured_qiyuan_dir = (
            self.storage.get_config("browser_app_data_dir")
            or os.environ.get("CHROMIUM_SDK_QIYUAN_DIR")
        )
        self.browser_app_data_dir = qiyuan_config.qiyuan_dir(configured_qiyuan_dir)
        self.launcher = BrowserLauncher(self.browser_app_data_dir)
        self.base_api_path = (
            base_api_path
            or os.environ.get("CHROMIUM_SDK_BASE_API")
            or DEFAULT_BASE_API_PATH
        )
        self._token = self._init_token()
        # seed config.json defaults (base_api_path / browser_base_path) if missing
        try:
            if qiyuan_config.inspect_qiyuan_dir(self.browser_app_data_dir)["valid"]:
                qiyuan_config.ensure_qiyuan_config(
                    self.base_api_path, browser_app_data_dir=self.browser_app_data_dir
                )
        except OSError:
            pass

    # ------------------------------------------------------------------ token
    def _init_token(self) -> str:
        """Resolve the static local token (env var > stored > newly generated)."""
        env_token = os.environ.get("CHROMIUM_SDK_TOKEN")
        if env_token:
            return env_token
        stored = self.storage.get_config("token")
        if stored:
            return stored
        token = secrets.token_urlsafe(32)
        self.storage.set_config("token", token)
        return token

    @property
    def token(self) -> str:
        return self._token

    def verify_token(self, value: Optional[str]) -> bool:
        return bool(value) and secrets.compare_digest(value, self._token)

    def browser_settings(self) -> Dict[str, Any]:
        return qiyuan_config.inspect_qiyuan_dir(self.browser_app_data_dir)

    def set_browser_app_data_dir(self, value: Optional[str]) -> Dict[str, Any]:
        root = qiyuan_config.qiyuan_dir(value or qiyuan_config.default_qiyuan_dir())
        self.storage.set_config("browser_app_data_dir", root)
        self.browser_app_data_dir = root
        self.launcher.set_browser_app_data_dir(root)
        return self.browser_settings()

    # ------------------------------------------------------------------ utils
    def _require_env(self, code: str) -> Dict[str, Any]:
        if not code:
            raise ValidationError("缺少必要参数: code")
        env = self.storage.get_environment(code)
        if not env:
            raise NotFoundError("环境不存在")
        return env

    def _normalize_proxy_fields(self, data: Dict[str, Any], *, updating: bool = False) -> Dict[str, Any]:
        """Normalize proxy_mode / proxy_code / custom_* for create/update."""
        mode = data.get("proxy_mode")
        if not mode:
            if data.get("proxy_code"):
                mode = "existing"
            elif data.get("custom_proxy_addr") and data.get("custom_proxy_port"):
                mode = "custom"
            elif updating and "proxy_mode" not in data and "proxy_code" not in data:
                return {}
            else:
                mode = "no_proxy"

        out: Dict[str, Any] = {"proxy_mode": mode}
        if mode == "existing":
            code = data.get("proxy_code") or ""
            if not code:
                raise ValidationError("请选择已添加的代理")
            if not self.storage.get_proxy(code):
                raise ValidationError(f"代理 code=\"{code}\" 不存在")
            out["proxy_code"] = code
            out["custom_proxy_type"] = None
            out["custom_proxy_addr"] = None
            out["custom_proxy_port"] = None
            out["custom_proxy_username"] = None
            out["custom_proxy_password"] = None
        elif mode == "custom":
            addr = (data.get("custom_proxy_addr") or "").strip()
            port = data.get("custom_proxy_port")
            if not addr or port in (None, ""):
                raise ValidationError("自定义代理需填写地址和端口")
            out["proxy_code"] = None
            out["custom_proxy_type"] = (data.get("custom_proxy_type") or "http").strip()
            out["custom_proxy_addr"] = addr
            out["custom_proxy_port"] = int(port)
            out["custom_proxy_username"] = (data.get("custom_proxy_username") or "").strip() or None
            out["custom_proxy_password"] = (data.get("custom_proxy_password") or "").strip() or None
        else:
            out["proxy_mode"] = "no_proxy"
            out["proxy_code"] = None
            out["custom_proxy_type"] = None
            out["custom_proxy_addr"] = None
            out["custom_proxy_port"] = None
            out["custom_proxy_username"] = None
            out["custom_proxy_password"] = None
        return out

    def _resolve_proxy(self, env: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        mode = env.get("proxy_mode") or ("existing" if env.get("proxy_code") else "no_proxy")
        if mode == "custom" and env.get("custom_proxy_addr") and env.get("custom_proxy_port"):
            return {
                "proxy_type": env.get("custom_proxy_type") or "http",
                "proxy_addr": env["custom_proxy_addr"],
                "proxy_port": env["custom_proxy_port"],
                "username": env.get("custom_proxy_username") or "",
                "password": env.get("custom_proxy_password") or "",
            }
        if mode == "existing" and env.get("proxy_code"):
            return self.storage.get_proxy(env["proxy_code"])
        return None

    def _enrich_env(self, env: Dict[str, Any]) -> Dict[str, Any]:
        running = self.launcher.is_running(env)
        # stale pid after direct window close / crashed process
        if not running and env.get("pid"):
            self.storage.set_runtime(env["code"], None, None)
            env = {**env, "pid": None, "debug_port": None}
        mode = env.get("proxy_mode") or ("existing" if env.get("proxy_code") else "no_proxy")
        return {
            "code": env["code"],
            "name": env["name"],
            "platform": env["platform"],
            "browser_version": env["browser_version"],
            "user_agent": env["user_agent"],
            "proxy_code": env.get("proxy_code"),
            "proxy_mode": mode,
            "custom_proxy_type": env.get("custom_proxy_type"),
            "custom_proxy_addr": env.get("custom_proxy_addr"),
            "custom_proxy_port": env.get("custom_proxy_port"),
            "custom_proxy_username": env.get("custom_proxy_username"),
            "custom_proxy_password": env.get("custom_proxy_password"),
            "open_home_page": bool(env["open_home_page"]),
            "enable_tabs": bool(env["enable_tabs"]),
            "remark": env["remark"],
            "tag_ids": env["tag_ids"],
            "status": "running" if running else "stopped",
            "pid": env["pid"] if running else None,
            "create_time": env["create_time"],
            "update_time": env["update_time"],
        }

    # ----------------------------------------------------------- environments
    def env_list(self, page: int = 1, page_size: int = 20, keyword: str = "") -> Dict[str, Any]:
        items, total = self.storage.list_environments(page, page_size, keyword)
        return {
            "items": [self._enrich_env(e) for e in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def env_create(self, **data: Any) -> Dict[str, Any]:
        name = data.get("name")
        if not name:
            raise ValidationError("缺少必要参数: name")

        proxy_fields = self._normalize_proxy_fields(data)

        platform = data.get("platform") or "Win32"
        browser_version = data.get("browser_version") or fp.DEFAULT_CHROME_VERSION
        user_agent = data.get("user_agent") or fp.generate_user_agent(platform, browser_version)
        # explicit fingerprint dict wins; otherwise random base + form overrides
        if data.get("fingerprint"):
            fingerprint = data["fingerprint"]
        else:
            fingerprint = fp.generate_fingerprint(platform)
            fingerprint.update(fp.build_fingerprint_payload(data))

        record = {
            "name": name,
            "platform": platform,
            "browser_version": browser_version,
            "user_agent": user_agent,
            **proxy_fields,
            "open_home_page": data.get("open_home_page", False),
            "enable_tabs": data.get("enable_tabs", False),
            "tabs": data.get("tabs", ""),
            "sync_user_info": data.get("sync_user_info", False),
            "cookie": data.get("cookie", ""),
            "launch_args": data.get("launch_args", ""),
            "remark": data.get("remark", ""),
            "tag_ids": data.get("tag_ids", []),
            "fingerprint": fingerprint,
        }
        env = self.storage.insert_environment(record)
        return {"code": env["code"]}

    def env_update(self, code: str, **fields: Any) -> Dict[str, Any]:
        env = self._require_env(code)
        proxy_touch = any(
            k in fields
            for k in (
                "proxy_mode", "proxy_code", "custom_proxy_type", "custom_proxy_addr",
                "custom_proxy_port", "custom_proxy_username", "custom_proxy_password",
            )
        )
        if proxy_touch:
            fields.update(self._normalize_proxy_fields(fields, updating=True))
        if ("platform" in fields or "browser_version" in fields) and "user_agent" not in fields:
            platform = fields.get("platform", env["platform"])
            version = fields.get("browser_version", env["browser_version"])
            fields["user_agent"] = fp.generate_user_agent(platform, version)
        # merge any fingerprint form fields into the stored fingerprint
        fp_payload = fp.build_fingerprint_payload(fields)
        if fp_payload or "platform" in fields:
            merged = dict(env.get("fingerprint") or {})
            merged.update(fp_payload)
            if "platform" in fields:
                merged["platform"] = fields["platform"]
            fields["fingerprint"] = merged
        self.storage.update_environment(code, fields)
        return {"code": code}

    def env_delete(self, code: str) -> Dict[str, Any]:
        env = self._require_env(code)
        if self.launcher.is_running(env):
            self.launcher.close(env)
        self.launcher.clear_cache(code)
        self.storage.delete_environment(code)
        return {"code": code}

    def env_detail(self, code: str) -> Dict[str, Any]:
        """Full environment for the edit form: enriched fields + flat fingerprint."""
        env = self._require_env(code)
        detail = self._enrich_env(env)
        detail.update({
            "fingerprint": env.get("fingerprint") or {},
            "tabs": env["tabs"],
            "sync_user_info": bool(env["sync_user_info"]),
            "cookie": env["cookie"],
            "launch_args": env["launch_args"],
        })
        return detail

    def env_randomize_fingerprint(self, code: str) -> Dict[str, Any]:
        env = self._require_env(code)
        new_fp = fp.generate_fingerprint(env["platform"])
        self.storage.update_environment(code, {"fingerprint": new_fp})
        return new_fp

    def env_open(self, code: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        env = self._require_env(code)
        if not env.get("browser_version"):
            raise ValidationError("该环境未配置内核版本")
        # ensure the launched browser calls back into our admin server
        status = self.browser_settings()
        if not status["valid"]:
            missing = [name for name, present in status["checks"].items() if not present]
            raise ValidationError(
                "浏览器应用数据目录无效，请在“浏览器设置”中配置 browser_app_data_dir；"
                f"缺失项: {', '.join(missing)}"
            )
        qiyuan_config.ensure_qiyuan_config(
            self.base_api_path, browser_app_data_dir=self.browser_app_data_dir
        )
        result = self.launcher.open(env, token=self._token, extra_args=args)
        self.storage.set_runtime(code, result["pid"], None)
        return result

    def env_close(self, code: str) -> Dict[str, Any]:
        env = self._require_env(code)
        if not self.launcher.is_running(env):
            raise ValidationError("浏览器未在运行")
        self.launcher.close(env)
        self.storage.set_runtime(code, None, None)
        return {"code": code}

    def env_status(self, code: str) -> Dict[str, Any]:
        env = self._require_env(code)
        running = self.launcher.is_running(env)
        if not running and env.get("pid"):
            self.storage.set_runtime(code, None, None)
        return {
            "code": code,
            "status": "running" if running else "stopped",
            "pid": env["pid"] if running else None,
        }

    def env_clear_cache(self, code: str) -> Dict[str, Any]:
        env = self._require_env(code)
        if self.launcher.is_running(env):
            self.launcher.close(env)
            self.storage.set_runtime(code, None, None)
        self.launcher.clear_cache(code)
        return {"code": code}

    # ----------------------------------------------------------------- proxies
    def proxy_list(self, page: int = 1, page_size: int = 20, keyword: str = "") -> Dict[str, Any]:
        items, total = self.storage.list_proxies(page, page_size, keyword)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def proxy_create(self, **data: Any) -> Dict[str, Any]:
        required = ("proxy_name", "proxy_type", "proxy_addr", "proxy_port")
        missing = [k for k in required if not data.get(k)]
        if missing:
            raise ValidationError("缺少必要参数: " + ", ".join(missing))
        proxy = self.storage.insert_proxy(data)
        return {"code": proxy["code"]}

    def proxy_update(self, code: str, **fields: Any) -> Dict[str, Any]:
        if not code:
            raise ValidationError("缺少必要参数: code")
        if not self.storage.update_proxy(code, fields):
            raise NotFoundError("代理不存在")
        return {"code": code}

    def proxy_delete(self, code: str) -> Dict[str, Any]:
        if not code:
            raise ValidationError("缺少必要参数: code")
        if not self.storage.delete_proxy(code):
            raise NotFoundError("代理不存在")
        return {"code": code}

    # ------------------------------------------------------------- fingerprint
    def generate_fingerprint(self, platform: str = "Win32") -> Dict[str, Any]:
        return fp.generate_fingerprint(platform)

    # =====================================================================
    #  Server callbacks — invoked by the launched browser via admin/server.py
    # =====================================================================
    def get_fingerprint_payload(self, uuid: str) -> Dict[str, Any]:
        """Build the nested fingerprint JSON the client browser consumes."""
        env = self._require_env(uuid)
        proxy = self._resolve_proxy(env)
        return fp.build_fingerprint_json(env, env.get("fingerprint") or {}, proxy)

    def get_encrypted_fingerprint(
        self,
        uuid: str,
        encrypt_type: str = "aes",
        version: str = "1.0",
        token: Optional[str] = None,
    ) -> str:
        from . import crypto  # lazy: needs pycryptodome
        payload = self.get_fingerprint_payload(uuid)
        if encrypt_type == "rsa":
            # AES(token派生key) 加密 + RSA 私钥签名；内核用内置公钥验签 + token 解密
            key = crypto.derive_aes_key_v2(token or self._token)
            return crypto.sign_encrypt_json(payload, key)
        if encrypt_type == "aes":
            key = None
            if version == "2.0":
                # v2: AES key derived from the fixed key + user auth token
                key = crypto.derive_aes_key_v2(token or self._token)
            return crypto.encrypt_json(payload, key=key)
        raise ValidationError(f"不支持的加密方式: {encrypt_type}")

    def report_error(self, title: str, detail: str = "", type_: str = "") -> Dict[str, Any]:
        if not title:
            raise ValidationError("缺少必要参数: title")
        code = self.storage.insert_error(title, detail, type_)
        return {"code": code}

    def update_tabs(self, md5: str, tabs: str) -> Dict[str, Any]:
        env = self.storage.get_environment(md5)
        if not env:
            return {"saved": False, "reason": "环境不存在"}
        if not env.get("enable_tabs"):
            return {"saved": False, "reason": "标签页功能已关闭"}
        self.storage.update_environment(md5, {"tabs": fp_dedup_tabs(tabs)})
        return {"saved": True}

    def record_status(self, uuid: str, status: str) -> Dict[str, Any]:
        """Kernel callback: opened/closed. Cleared pid on close so list shows 打开."""
        env = self.storage.get_environment(uuid)
        if not env:
            return {"updated": False}
        opened = status in ("open", "opened", "打开")
        if opened:
            # keep existing pid from env_open; nothing to set here
            return {"updated": True, "status": "opened"}
        self.storage.set_runtime(uuid, None, None)
        return {"updated": True, "status": "closed"}

    def browser_home_data(self, md5: str) -> Dict[str, Any]:
        """Start-page data (browser / fingerprint / proxy) for the home page."""
        env = self.storage.get_environment(md5)
        if not env:
            raise NotFoundError("浏览器实例不存在")
        proxy = self._resolve_proxy(env)
        return build_home_data(env, env.get("fingerprint") or {}, proxy)

    def browser_error_data(self, code: str) -> Dict[str, Any]:
        rec = self.storage.get_error(code)
        if rec:
            return {"code": code, "title": rec["title"], "error_time": rec["create_time"] or ""}
        return {"code": code, "title": "未知错误", "error_time": ""}

    def ip_geo(self, ip: str = "") -> Dict[str, Any]:
        from . import geo  # lazy: needs httpx
        return geo.lookup_ip_geo(ip)

    def check_proxy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        from . import geo  # lazy: needs httpx
        return geo.check_proxy(data)

    def close(self) -> None:
        self.storage.close()


# --- tab de-duplication (ported from backend _dedup_tabs) --------------------
from urllib.parse import urlparse  # noqa: E402

_BLOCKED_TAB_PATH_PREFIXES = ("/api/v1/browser/home/",)
_BLOCKED_TAB_DOMAIN_KEYWORDS = (
    "localhost",
    "127.0.0.1",
    "usefullc.com",
    "chrome-extension",
)


def _is_blocked_tab(url: str) -> bool:
    """Match backend filtering and reject values that are not useful web tabs."""
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return True
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return True
    domain = parsed.netloc.lower()
    if any(parsed.path.startswith(prefix) for prefix in _BLOCKED_TAB_PATH_PREFIXES):
        return True
    return any(keyword in domain for keyword in _BLOCKED_TAB_DOMAIN_KEYWORDS)


def fp_dedup_tabs(tabs: str, limit: int = 5) -> str:
    """Filter internal/start pages and keep one URL per domain, max ``limit``."""
    seen: set[str] = set()
    result: List[str] = []
    for line in (tabs or "").splitlines():
        url = line.strip()
        if not url or _is_blocked_tab(url):
            continue
        domain = urlparse(url).netloc.lower()
        if domain in seen:
            continue
        seen.add(domain)
        result.append(url)
        if len(result) >= limit:
            break
    return "\n".join(result)


# --- start-page data mapping (ported from backend browser_home.py) -----------
_PLATFORM_MAP = {"Win32": "Windows", "MacIntel": "macOS", "Linux x86_64": "Linux"}
_PROXY_MODE_MAP = {"no_proxy": "本地直连", "existing": "集成代理", "custom": "自定义"}
_WEBRTC_MAP = {"ip": "基于IP", "real": "真实", "disabled": "禁用", "transform_google": "转发"}
_WEBGL_MAP = {"real": "真实", "custom": "自定义", "disabled": "禁用"}
_WEBGPU_MAP = {"basegl": "基于WebGL", "real": "真实", "custom": "自定义"}
_TYPE3_MAP = {"ip": "基于IP", "real": "真实", "custom": "自定义"}
_UI_LANG_MAP = {"language": "基于语言", "real": "真实", "custom": "自定义"}
_SCREEN_MAP = {"real": "真实", "custom": "自定义"}
_TLS_MAP = {"disabled": "关闭", "enabled": "启用"}


def _t(val: Any, mapping: Dict[Any, str]) -> str:
    return mapping.get(val, val) if val else "-"


def _rand(val: Any) -> str:
    if val is None:
        return "0"
    try:
        return "随机" if float(val) != 0 else "0"
    except (TypeError, ValueError):
        return str(val)


def _noise(val: Any) -> str:
    """Font / audio noise display: only 随机 or 关闭."""
    if val is None or val is False or val == "" or val == "0":
        return "关闭"
    try:
        return "关闭" if float(val) == 0 else "随机"
    except (TypeError, ValueError):
        return "随机" if val else "关闭"


def _format_custom_parts(value: Optional[str]) -> str:
    """Custom WebGL/WebGPU: one sub-item per line under 自定义."""
    parts = [p.strip() for p in (value or "").split("|") if p.strip()]
    if not parts:
        return "自定义"
    return "自定义\n" + "\n".join(parts)


def _format_font_noise(fp: Dict[str, Any]) -> str:
    text = _noise(fp.get("font"))
    fl = fp.get("font_list")
    if isinstance(fl, str) and fl.strip():
        try:
            fl = json.loads(fl)
        except (ValueError, TypeError):
            fl = None
    if isinstance(fl, list) and fl:
        text = f"{text}（{len(fl)} 个字体）"
    return text


def build_home_data(env: Dict[str, Any], fp: Dict[str, Any],
                    proxy: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    proxy_mode = env.get("proxy_mode") or ("existing" if proxy else "no_proxy")
    proxy_data: Dict[str, Any] = {"proxy_mode": proxy_mode, "md5": env.get("code", "")}
    if proxy:
        proxy_data.update({
            "proxy_type": proxy.get("proxy_type") or "http",
            "proxy_addr": proxy.get("proxy_addr") or "",
            "proxy_port": proxy.get("proxy_port") or 0,
            "proxy_username": proxy.get("username") or "",
            "proxy_password": proxy.get("password") or "",
        })

    if fp.get("webgl_type") == "custom" and fp.get("webgl_value"):
        webgl = _format_custom_parts(fp.get("webgl_value"))
    else:
        webgl = _t(fp.get("webgl_type"), _WEBGL_MAP)

    if fp.get("webgpu_type") == "custom" and fp.get("webgpu_value"):
        webgpu = _format_custom_parts(fp.get("webgpu_value"))
    else:
        webgpu = _t(fp.get("webgpu_type"), _WEBGPU_MAP)

    tz_type, tz_val = _t(fp.get("timezone_type"), _TYPE3_MAP), fp.get("timezone_value")
    geo_type, geo_val = _t(fp.get("geo_location_type"), _TYPE3_MAP), fp.get("geo_location_value")
    lang_type, lang_val = _t(fp.get("language_type"), _TYPE3_MAP), fp.get("language_value")
    ui_type, ui_val = _t(fp.get("ui_language_type"), _UI_LANG_MAP), fp.get("ui_language_value")
    sc_type, sc_val = _t(fp.get("screen_resolution_type"), _SCREEN_MAP), fp.get("screen_resolution_value")

    devs = fp.get("media_devices")
    media_devices = f"随机（{len(devs)} 个设备）" if devs else "关闭"
    hw = fp.get("hardware_info") or {}
    tls_value = fp.get("tls_value") or ""

    return {
        "browser": {
            "name": env.get("name") or "-",
            "proxy_mode_cn": _t(proxy_mode, _PROXY_MODE_MAP),
            "sync_user": "启用" if env.get("sync_user_info") else "关闭",
            "tags": "-",
            "launch_args": env.get("launch_args") or "-",
            "remark": env.get("remark") or "-",
        },
        "fingerprint": {
            "platform": _t(fp.get("platform") or env.get("platform"), _PLATFORM_MAP),
            "browser_version": env.get("browser_version") or "-",
            "user_agent": env.get("user_agent") or "-",
            "webrtc": _t(fp.get("webrtc"), _WEBRTC_MAP),
            "webgl": webgl,
            "webgpu": webgpu,
            "timezone": f"{tz_type} - {tz_val}" if tz_val else tz_type,
            "geo": f"{geo_type} - {geo_val.replace('|', ', ')}" if geo_val else geo_type,
            "language": f"{lang_type} - {lang_val}" if lang_val else lang_type,
            "ui_language": f"{ui_type} - {ui_val}" if ui_val else ui_type,
            "screen": f"{sc_type} - {sc_val.replace('|', ' x ')}" if sc_val else sc_type,
            "font": _format_font_noise(fp),
            "canvas": _rand(fp.get("canvas")),
            "audio": _noise(fp.get("audio")),
            "client_rects": _rand(fp.get("client_rects")),
            "speech_voices": "随机" if fp.get("speech_voices") else "关闭",
            "media_devices": media_devices,
            "local_port_access": (
                "关闭"
                if (fp.get("local_port_access") or "all") == "all"
                else (
                    f"开启（白名单：{fp.get('local_port_access')}）"
                    if (fp.get("local_port_access") or "all") not in ("none", "all", "")
                    else "开启"
                )
            ),
            "do_not_track": "开启" if fp.get("do_not_track", 1) else "关闭",
            "cpu_cores": hw.get("cpu_cores") or "真实",
            "memory_gb": f"{hw.get('memory_gb')} GB" if hw.get("memory_gb") else "真实",
            "tls": _t(fp.get("tls_type"), _TLS_MAP),
            "tls_value": tls_value or "-",
        },
        "proxy": proxy_data,
    }
