"""Management admin for the Chromium SDK.

A thin FastAPI app that exposes all 14 operations over HTTP using the same
paths and ``{success, data|error}`` envelope as the Electron client's open API,
and serves a single-page management UI. Everything is driven through
:class:`chromium_sdk.ChromiumClient`, so the HTTP layer and the in-process SDK
share identical logic and the same SQLite store.

Run:
    uvicorn admin.server:app --reload
or:
    python -m admin.server
"""

from __future__ import annotations

import os
import shutil
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from chromium_sdk import ChromiumClient
from chromium_sdk.errors import SdkError
from chromium_sdk.gpu_fingerprint import get_gpu_options
from admin.logging_setup import configure_logging

DATA_DIR = os.environ.get("CHROMIUM_SDK_DATA_DIR")
BASE_API_PATH = os.environ.get("CHROMIUM_SDK_BASE_API")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

@asynccontextmanager
async def lifespan(app: FastAPI):
    log_path = configure_logging(client.data_dir)
    logging.getLogger(__name__).info("管理服务启动；数据库: %s；日志: %s", client.storage.db_path, log_path)
    try:
        yield
    finally:
        logging.getLogger(__name__).info("管理服务停止")


app = FastAPI(title="Chromium SDK Admin", version="0.1.0", lifespan=lifespan)
client = ChromiumClient(data_dir=DATA_DIR, base_api_path=BASE_API_PATH)


def _initialize_default_browser_dir() -> None:
    """Seed the default browser directory once, preserving any existing files."""
    from chromium_sdk import qiyuan_config

    target = qiyuan_config.default_qiyuan_dir()
    source = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "qiyuan"))
    # Older setups often pointed at the bundled source directory itself.
    if os.path.normcase(client.browser_app_data_dir) == os.path.normcase(source):
        client.set_browser_app_data_dir(target)
    if os.path.normcase(client.browser_app_data_dir) != os.path.normcase(target):
        return  # A manually selected directory is managed by the user.
    if qiyuan_config.inspect_qiyuan_dir(target)["valid"]:
        if client.storage.get_config("default_browser_dir_initialized") != "1":
            client.storage.set_config("default_browser_dir_initialized", "1")
        return

    for name in ("client", "config", "extends"):
        source_dir = os.path.join(source, name)
        if not os.path.isdir(source_dir):
            raise RuntimeError(f"缺少浏览器初始化目录: {source_dir}")
    for name in ("client", "config", "extends"):
        source_dir = os.path.join(source, name)
        for root, dirs, files in os.walk(source_dir):
            relative = os.path.relpath(root, source_dir)
            destination = os.path.join(target, name, relative)
            os.makedirs(destination, exist_ok=True)
            for filename in files:
                output = os.path.join(destination, filename)
                if not os.path.exists(output):
                    shutil.copy2(os.path.join(root, filename), output)

    if not qiyuan_config.inspect_qiyuan_dir(target)["valid"]:
        raise RuntimeError(f"浏览器初始化后目录仍不完整: {target}")
    client.storage.set_config("default_browser_dir_initialized", "1")
    qiyuan_config.ensure_qiyuan_config(client.base_api_path, browser_app_data_dir=target)


_initialize_default_browser_dir()


def ok(data: Any = None) -> JSONResponse:
    """Open-API envelope (matches the Electron client)."""
    return JSONResponse({"success": True, "data": data})


def err(message: str) -> JSONResponse:
    return JSONResponse({"success": False, "error": message})


def api_ok(data: Any = None, message: str = "OK") -> JSONResponse:
    """Backend-style ApiResponse envelope (for /api/v1/* the browser calls)."""
    return JSONResponse({"code": 200, "message": message, "data": data, "success": True})


def api_err(message: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"code": code, "message": message, "data": None, "success": False})


def _bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    return auth[7:] if auth.startswith("Bearer ") else None


async def _run(handler: Callable[[Dict[str, Any]], Any], request: Request) -> JSONResponse:
    """Parse JSON body, invoke handler, wrap result/errors in the envelope."""
    try:
        body = await request.json() if await request.body() else {}
    except Exception:
        body = {}
    try:
        return ok(handler(body or {}))
    except SdkError as exc:
        return err(str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logging.getLogger(__name__).exception("请求处理失败")
        return err(f"内部错误: {exc}")


def _qp(request: Request) -> Dict[str, str]:
    return dict(request.query_params)


# ----------------------------------------------------------------- UI / static
@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/open/settings/browser")
def browser_settings() -> JSONResponse:
    return ok(client.browser_settings())


@app.post("/open/settings/browser")
async def browser_settings_save(request: Request) -> JSONResponse:
    return await _run(
        lambda b: client.set_browser_app_data_dir(b.get("browser_app_data_dir")),
        request,
    )


# ---- browser start page / error page (browser_base_path -> this server) ----
# The kernel navigates to {browser_base_path}/pages/home.html?md5=... and
# {browser_base_path}/pages/error.html?code=... These pages fetch same-origin.
@app.get("/pages/home.html", response_class=HTMLResponse)
def page_home() -> HTMLResponse:
    return HTMLResponse(HOME_PAGE_HTML)


@app.get("/pages/error.html", response_class=HTMLResponse)
def page_error() -> HTMLResponse:
    return HTMLResponse(ERROR_PAGE_HTML)


@app.get("/api/v1/browser/home-data/{md5}")
def browser_home_data(md5: str) -> JSONResponse:
    try:
        return api_ok(client.browser_home_data(md5))
    except SdkError as exc:
        return api_err(str(exc), code=404)


@app.get("/api/v1/browser/error-data/{code}")
def browser_error_data(code: str) -> JSONResponse:
    return api_ok(client.browser_error_data(code))


@app.get("/api/check-network")
def check_network() -> JSONResponse:
    """Direct (no-proxy) IP geo for the start page. No auth."""
    return JSONResponse(client.ip_geo(""))


# ----------------------------------------------------------------- environments
@app.get("/open/env/list")
def env_list(request: Request) -> JSONResponse:
    q = _qp(request)
    try:
        return ok(client.env_list(
            page=int(q.get("page", 1)),
            page_size=int(q.get("page_size", 20)),
            keyword=q.get("keyword", ""),
        ))
    except SdkError as exc:
        return err(str(exc))


@app.get("/open/env/detail")
def env_detail(request: Request) -> JSONResponse:
    code = _qp(request).get("code", "")
    try:
        return ok(client.env_detail(code))
    except SdkError as exc:
        return err(str(exc))


@app.post("/open/env/create")
async def env_create(request: Request) -> JSONResponse:
    return await _run(lambda b: client.env_create(**b), request)


@app.post("/open/env/update")
async def env_update(request: Request) -> JSONResponse:
    return await _run(
        lambda b: client.env_update(b.pop("code", ""), **b), request
    )


@app.post("/open/env/delete")
async def env_delete(request: Request) -> JSONResponse:
    return await _run(lambda b: client.env_delete(b.get("code", "")), request)


@app.post("/open/env/randomize_fingerprint")
async def env_randomize(request: Request) -> JSONResponse:
    return await _run(
        lambda b: client.env_randomize_fingerprint(b.get("code", "")), request
    )


@app.post("/open/env/open")
async def env_open(request: Request) -> JSONResponse:
    return await _run(
        lambda b: client.env_open(b.get("code", ""), args=b.get("args")), request
    )


@app.post("/open/env/close")
async def env_close(request: Request) -> JSONResponse:
    return await _run(lambda b: client.env_close(b.get("code", "")), request)


@app.get("/open/env/status")
def env_status(request: Request) -> JSONResponse:
    code = _qp(request).get("code", "")
    try:
        return ok(client.env_status(code))
    except SdkError as exc:
        return err(str(exc))


@app.post("/open/env/clear_cache")
async def env_clear_cache(request: Request) -> JSONResponse:
    return await _run(lambda b: client.env_clear_cache(b.get("code", "")), request)


# ----------------------------------------------------------------------- proxies
@app.get("/open/proxy/list")
def proxy_list(request: Request) -> JSONResponse:
    q = _qp(request)
    return ok(client.proxy_list(
        page=int(q.get("page", 1)),
        page_size=int(q.get("page_size", 20)),
        keyword=q.get("keyword", ""),
    ))


@app.post("/open/proxy/create")
async def proxy_create(request: Request) -> JSONResponse:
    return await _run(lambda b: client.proxy_create(**b), request)


@app.post("/open/proxy/update")
async def proxy_update(request: Request) -> JSONResponse:
    return await _run(
        lambda b: client.proxy_update(b.pop("code", ""), **b), request
    )


@app.post("/open/proxy/delete")
async def proxy_delete(request: Request) -> JSONResponse:
    return await _run(lambda b: client.proxy_delete(b.get("code", "")), request)


# ------------------------------------------------------------------- fingerprint
@app.post("/open/fingerprint/generate")
async def fingerprint_generate(request: Request) -> JSONResponse:
    return await _run(
        lambda b: client.generate_fingerprint(b.get("platform", "Win32")), request
    )


@app.get("/open/gpu-options")
def open_gpu_options() -> JSONResponse:
    return ok(get_gpu_options())


@app.get("/api/v1/browser/gpu-options")
def browser_gpu_options() -> JSONResponse:
    """Same payload as backend GET /api/v1/browser/gpu-options."""
    return api_ok(get_gpu_options())


# =====================================================================
#  Server callbacks — called by the launched client browser
# =====================================================================

@app.get("/api/v1/browser/md5/{uuid}")
def browser_md5(
    uuid: str,
    request: Request,
    secure: bool = True,
    encrypt_type: str = "aes",
    version: str = "1.0",
) -> JSONResponse:
    """拉取指纹。Authorization: Bearer {token}

    - secure: 是否加密，默认 true（是）；false 则返回明文，encrypt_type 忽略。
    - encrypt_type: 加密方式，默认 aes，支持 aes / rsa。
    - version: 算法版本，默认 1.0；2.0 且 aes 时 key 由固定key+"_qiyuan_"+token 派生。
    """
    token = _bearer(request)
    if not client.verify_token(token):
        return api_err("unauthorized", code=401)
    try:
        if not secure:
            return api_ok(client.get_fingerprint_payload(uuid))
        return api_ok(client.get_encrypted_fingerprint(uuid, encrypt_type, version, token))
    except SdkError as exc:
        code = 404 if "不存在" in str(exc) else 400
        return api_err(str(exc), code=code)


@app.post("/api/v1/browser/error/report")
async def browser_error_report(request: Request) -> JSONResponse:
    """错误上报（无需 token）。body {title, detail, type} -> {data:{code}}"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        data = client.report_error(
            body.get("title", ""), body.get("detail", ""), body.get("type", "")
        )
        return api_ok(data, message="错误已上报")
    except SdkError as exc:
        return api_err(str(exc))


@app.post("/api/v1/client/browser/tabs")
async def client_browser_tabs(request: Request) -> JSONResponse:
    """标签上报。过滤内部/无效链接，按域名去重并最多保存 5 条。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    result = client.update_tabs(body.get("md5", ""), body.get("tabs", ""))
    return api_ok(result)


@app.post("/api/check-proxy")
async def check_proxy(request: Request) -> JSONResponse:
    """代理检测。body {proxy_type, proxy_addr, proxy_port, username, password}"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    return JSONResponse(client.check_proxy(body))


@app.get("/api/ip-geo")
def ip_geo(request: Request, ip: str = "") -> JSONResponse:
    """IP 地理。Bearer 鉴权。"""
    if not client.verify_token(_bearer(request)):
        return JSONResponse({"success": False, "error": "unauthorized"})
    return JSONResponse(client.ip_geo(ip))


@app.post("/api/browser/status")
async def browser_status(request: Request) -> JSONResponse:
    """开关状态。body {uuid, status:"opened"|"closed"}"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    uuid = body.get("uuid")
    if not uuid:
        return JSONResponse({"success": False, "error": "missing uuid"})
    client.record_status(uuid, str(body.get("status", "")))
    return JSONResponse({"success": True})


# =====================================================================
#  Browser start page / error page (ported from
#  front-extends/fingerprint-manager/pages, using same-origin fetch
#  instead of the chrome.runtime extension bridge)
# =====================================================================

HOME_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>浏览器起始页</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; min-height: 100vh; padding: 0 0 40px; color: #333; }
    .ip-banner { background: linear-gradient(135deg, #2845d4 0%, #1a2fa8 100%); padding: 36px 20px; text-align: center; color: #fff; position: relative; overflow: hidden; }
    .ip-banner-inner { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center; gap: 8px; }
    .ip-loading { display: flex; align-items: center; gap: 10px; font-size: 15px; opacity: .8; }
    .spin { width: 20px; height: 20px; border: 2px solid rgba(255,255,255,.3); border-top-color: #fff; border-radius: 50%; animation: spin .8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .container { max-width: 960px; margin: 0 auto; padding: 24px 20px 0; }
    .card { background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,.06); }
    .card-title { font-size: 16px; font-weight: 600; color: #409eff; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid #e8f0fe; }
    .info-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 2px 0; }
    .info-item { display: flex; align-items: baseline; padding: 7px 0; border-bottom: 1px solid #f5f5f5; }
    .info-item.full { grid-column: 1 / -1; }
    .info-label { color: #909399; font-size: 13px; min-width: 110px; flex-shrink: 0; }
    .info-value { color: #303133; font-size: 13px; word-break: break-all; white-space: pre-line; line-height: 1.5; }
    .info-value.ua { font-size: 11px; color: #606266; line-height: 1.6; white-space: pre-wrap; }
    #err-tip { color: rgba(255,255,255,.75); font-size: 14px; padding: 20px; }
  </style>
</head>
<body>
<div class="ip-banner">
  <div id="ip-section" class="ip-banner-inner">
    <div class="ip-loading"><div class="spin"></div><span>IP 检测中...</span></div>
  </div>
</div>
<div class="container" id="main-content" style="display:none"></div>
<script>
(function () {
  var md5 = new URLSearchParams(location.search).get('md5') || '';
  function getJSON(url) { return fetch(url).then(function (r) { return r.json(); }); }
  function postJSON(url, body) { return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(function (r) { return r.json(); }); }

  var COUNTRY_CN = { 'US':'美国','CN':'中国','JP':'日本','KR':'韩国','SG':'新加坡','HK':'香港','TW':'台湾','DE':'德国','GB':'英国','FR':'法国','RU':'俄罗斯','AU':'澳大利亚','CA':'加拿大','BR':'巴西','IN':'印度','TH':'泰国','MY':'马来西亚','ID':'印度尼西亚','VN':'越南','PH':'菲律宾','NL':'荷兰','IT':'意大利','ES':'西班牙','SE':'瑞典','CH':'瑞士','TR':'土耳其' };
  var CITY_CN = { 'Beijing':'北京','Shanghai':'上海','Singapore':'新加坡','Tokyo':'东京','Seoul':'首尔','Hong Kong':'香港','New York':'纽约','Los Angeles':'洛杉矶','London':'伦敦','Paris':'巴黎' };
  function flagEmoji(code) { if (!code || code.length !== 2) return ''; var c = code.toUpperCase(); return String.fromCodePoint(0x1F1E6 + c.charCodeAt(0) - 65, 0x1F1E6 + c.charCodeAt(1) - 65); }

  function renderIpSuccess(r) {
    var sec = document.getElementById('ip-section');
    var countryCn = COUNTRY_CN[r.country_code] || r.country || '-';
    var cityCn = CITY_CN[r.city] || r.city || '-';
    var flagImg = (r.flag && r.flag.img) || '';
    var tzId = (r.timezone && r.timezone.id) || '';
    var tzUtc = (r.timezone && r.timezone.utc) || '';
    var flag = flagImg ? '<img src="' + flagImg + '" style="height:22px;vertical-align:middle;margin-right:6px;border-radius:2px">' : '<span style="font-size:22px;margin-right:6px">' + flagEmoji(r.country_code) + '</span>';
    var tzSuffix = (tzUtc || '') + (tzId ? ('，' + tzId) : '');
    sec.innerHTML =
      '<div style="display:flex;flex-direction:column;align-items:center;gap:8px">' +
        '<div style="display:flex;align-items:center;gap:10px">' + flag +
          '<span style="font-size:28px;font-weight:700;letter-spacing:1px;font-family:monospace">' + r.ip + '</span>' +
          '<button id="qy-copy-btn" style="background:rgba(255,255,255,.2);border:none;border-radius:6px;padding:4px 8px;cursor:pointer;color:#fff;font-size:13px">复制</button>' +
        '</div>' +
        '<div style="font-size:15px;opacity:.85">' + countryCn + ' / ' + (r.region || '') + ' / ' + cityCn + '</div>' +
        '<div style="font-size:13px;opacity:.65;display:flex;gap:16px"><span id="qy-clock"></span></div>' +
      '</div>';
    var btn = document.getElementById('qy-copy-btn');
    if (btn) btn.addEventListener('click', function () { navigator.clipboard.writeText(r.ip).then(function () { btn.textContent = '✓ 已复制'; setTimeout(function () { btn.textContent = '复制'; }, 1500); }); });
    if (tzId) {
      var fmt = new Intl.DateTimeFormat('zh-CN', { timeZone: tzId, year:'numeric', month:'long', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12: false });
      var tick = function () { var el = document.getElementById('qy-clock'); if (el) el.textContent = fmt.format(new Date()) + (tzSuffix ? '（' + tzSuffix + '）' : ''); };
      tick(); setInterval(tick, 1000);
    }
  }
  function renderIpError(error, addr) {
    document.getElementById('ip-section').innerHTML =
      '<div style="display:flex;flex-direction:column;align-items:center;gap:4px">' +
        '<div style="font-size:22px">⚠️</div>' +
        '<div style="font-size:15px;font-weight:600">IP 检测失败' + (addr ? '（' + addr + '）' : '') + '</div>' +
        '<div style="font-size:13px;opacity:.75">' + error + '</div>' +
        '<div style="font-size:12px;opacity:.6">请核实代理设置是否正确</div>' +
      '</div>';
  }
  function renderIpChecking() {
    document.getElementById('ip-section').innerHTML = '<div class="ip-loading"><div class="spin"></div><span>正在检测 IP…</span></div>';
  }
  function checkIp(proxyData) {
    var mode = proxyData ? proxyData.proxy_mode : 'existing';
    renderIpChecking();
    var addr = proxyData && proxyData.proxy_addr && proxyData.proxy_port ? proxyData.proxy_addr + ':' + proxyData.proxy_port : '';
    var promise = mode === 'no_proxy'
      ? getJSON('/api/check-network')
      : postJSON('/api/check-proxy', { proxy_type: proxyData.proxy_type || 'http', proxy_addr: proxyData.proxy_addr || '', proxy_port: Number(proxyData.proxy_port) || 0, username: proxyData.proxy_username || '', password: proxyData.proxy_password || '' });
    promise.then(function (res) {
      if (res.success) renderIpSuccess(res); else renderIpError(res.error || '未知错误', addr);
    }).catch(function (e) { renderIpError('无法连接IP检测服务（' + e.message + '）', addr); });
  }
  function row(label, value, full) {
    var text = (value == null || value === '') ? '-' : String(value);
    var isFull = !!full || text.indexOf('\n') >= 0;
    return '<div class="info-item' + (isFull ? ' full' : '') + '"><span class="info-label">' + label + '</span><span class="info-value' + (full && text.indexOf('\n') < 0 && text.length > 60 ? ' ua' : '') + '">' + text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</span></div>';
  }
  function renderMain(data) {
    var b = data.browser || {}; var fp = data.fingerprint || {};
    var mainEl = document.getElementById('main-content'); mainEl.style.display = '';
    document.title = b.name || '浏览器起始页';
    var envRows = [ row('环境名称', b.name || '-'), row('代理方式', b.proxy_mode_cn || '-'), row('同步用户信息', b.sync_user || '-'), row('标签', b.tags || '-') ];
    if (b.launch_args && b.launch_args !== '-') envRows.push(row('启动参数', b.launch_args, true));
    if (b.remark && b.remark !== '-') envRows.push(row('备注', b.remark, true));
    var fpRows = [ row('平台', fp.platform || '-'), row('版本', fp.browser_version || '-'), row('WebRTC', fp.webrtc || '-'), row('WebGL', fp.webgl || '-'), row('WebGPU', fp.webgpu || '-'), row('时区', fp.timezone || '-'), row('地理位置', fp.geo || '-'), row('语言', fp.language || '-'), row('界面语言', fp.ui_language || '-'), row('屏幕分辨率', fp.screen || '-'), row('字体噪音', fp.font || '-'), row('Canvas 噪声', fp.canvas || '-'), row('音频噪音', fp.audio || '-'), row('ClientRects', fp.client_rects || '-'), row('Speech Voices', fp.speech_voices || '-'), row('媒体设备', fp.media_devices || '-'), row('端口扫描保护', fp.local_port_access || '-'), row('Do Not Track', fp.do_not_track || '-'), row('CPU 核心数', fp.cpu_cores || '-'), row('内存', fp.memory_gb || '-'), row('禁用TLS特性', fp.tls || '-') ];
    mainEl.innerHTML =
      '<div class="card"><div class="card-title">🖥 环境信息</div><div class="info-grid">' + envRows.join('') + '</div></div>' +
      '<div class="card"><div class="card-title">🔏 指纹信息</div><div class="info-grid">' + fpRows.join('') + '</div>' +
        '<div class="info-grid" style="margin-top:8px">' + row('User Agent', fp.user_agent || '-', true) + '</div></div>';
  }
  getJSON('/api/v1/browser/home-data/' + encodeURIComponent(md5))
    .then(function (resp) {
      if (resp && resp.code === 200 && resp.data) { renderMain(resp.data); checkIp(resp.data.proxy || null); }
      else { document.getElementById('ip-section').innerHTML = '<div id="err-tip">数据加载失败：' + (resp && resp.message ? resp.message : '未知错误') + '</div>'; }
    })
    .catch(function (e) { document.getElementById('ip-section').innerHTML = '<div id="err-tip">无法连接服务：' + e.message + '</div>'; });
})();
</script>
</body>
</html>"""


ERROR_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>启动异常</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
    .error-card { background: #fff; border-radius: 16px; padding: 40px; max-width: 520px; width: 100%; box-shadow: 0 8px 32px rgba(0,0,0,.15); text-align: center; }
    .error-icon { font-size: 52px; margin-bottom: 16px; }
    .error-title { font-size: 20px; font-weight: 700; color: #303133; margin-bottom: 28px; line-height: 1.5; }
    .info-block { background: #f4f4f5; border-radius: 10px; padding: 16px 20px; text-align: left; margin-bottom: 12px; }
    .info-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
    .info-value { font-size: 15px; color: #303133; font-weight: 500; word-break: break-all; }
    .code-value { font-size: 22px; font-weight: 700; color: #409eff; letter-spacing: 3px; }
    .tips { margin-top: 20px; padding: 14px 18px; background: #fdf6ec; border: 1px solid #faecd8; border-radius: 8px; text-align: left; }
    .tips-title { font-size: 13px; font-weight: 600; color: #e6a23c; margin-bottom: 8px; }
    .tips ul { list-style: none; padding: 0; }
    .tips li { font-size: 13px; color: #909399; padding: 2px 0; }
    .tips li::before { content: "\2022"; color: #f0a540; margin-right: 8px; }
    .loading { color: #909399; font-size: 14px; }
  </style>
</head>
<body>
<div class="error-card" id="card">
  <div class="error-icon">⚠️</div>
  <div class="error-title loading">加载中...</div>
</div>
<script>
(function () {
  var code = new URLSearchParams(location.search).get('code') || '';
  function getJSON(url) { return fetch(url).then(function (r) { return r.json(); }); }
  function render(data) {
    var timeBlock = data.error_time ? '<div class="info-block"><div class="info-label">记录时间</div><div class="info-value">' + data.error_time + '</div></div>' : '';
    document.getElementById('card').innerHTML =
      '<div class="error-icon">&#9888;&#65039;</div>' +
      '<div class="error-title">' + (data.title || '未知错误') + '</div>' +
      '<div class="info-block"><div class="info-label">错误编号</div><div class="info-value code-value">' + (data.code || code) + '</div></div>' +
      timeBlock +
      '<div class="tips"><div class="tips-title">遇到问题？</div><ul>' +
        '<li>请将错误编号提供给技术支持以便快速定位</li>' +
        '<li>确认后端服务是否已启动并正常运行</li>' +
        '<li>检查网络连接和代理配置是否正确</li>' +
        '<li>尝试重新启动浏览器</li>' +
      '</ul></div>';
  }
  function renderFallback(msg) {
    document.getElementById('card').innerHTML =
      '<div class="error-icon">&#9888;&#65039;</div><div class="error-title">启动异常</div>' +
      '<div class="info-block"><div class="info-label">错误编号</div><div class="info-value code-value">' + code + '</div></div>' +
      '<div class="tips"><div class="tips-title">提示</div><ul><li>' + msg + '</li><li>请联系技术支持</li></ul></div>';
  }
  if (!code) { renderFallback('缺少错误编号'); return; }
  getJSON('/api/v1/browser/error-data/' + encodeURIComponent(code))
    .then(function (resp) { if (resp && resp.code === 200 && resp.data) render(resp.data); else renderFallback('数据加载失败'); })
    .catch(function (e) { renderFallback('无法连接服务：' + e.message); });
})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9003)
