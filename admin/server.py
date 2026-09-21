"""Qiyuan SDK management app; server and local routes live in separate modules.

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
from urllib.parse import urlparse

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from admin.event_loop import configure_windows_event_loop

# Resolve command-line overrides before qiyuan_config is imported.  These are
# intentionally limited to SDK runtime settings; the HTTP listener address is
# derived from base_local_api_path in the configuration.
def _command_line_value(*names: str) -> str | None:
    for name in names:
        prefix = name + "="
        for index, argument in enumerate(sys.argv):
            if argument == name:
                if index + 1 >= len(sys.argv):
                    raise RuntimeError(f"{name} requires a value")
                return sys.argv[index + 1]
            if argument.startswith(prefix):
                return argument[len(prefix):]
    return None


_config_value = _command_line_value("--config")
if _config_value:
    os.environ["QIYUAN_CONFIG_PATH"] = os.path.abspath(_config_value)
_api_value = _command_line_value("--base-api-path")
if _api_value:
    os.environ["QIYUAN_BASE_API_PATH"] = _api_value.rstrip("/")
_local_api_value = _command_line_value("--base-local-api-path")
if _local_api_value:
    os.environ["QIYUAN_BASE_LOCAL_API_PATH"] = _local_api_value.rstrip("/")
_token_value = _command_line_value("--token")
if _token_value:
    os.environ["QIYUAN_CLI_TOKEN"] = _token_value

if "QIYUAN_CONFIG_PATH" not in os.environ:
    _server_config = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "browser-config-server.json"))
    if os.path.isfile(_server_config):
        os.environ["QIYUAN_CONFIG_PATH"] = _server_config

# QyBrowser opens and sometimes cancels loopback requests during startup.
# On Windows, the Proactor/AcceptEx path can lose the listening socket after
# such a cancellation (WinError 64). Configure the policy before Uvicorn
# creates its server loop.
configure_windows_event_loop()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sdk import ChromiumClient
from sdk import qiyuan_config
from admin.logging_setup import configure_logging

DATA_DIR = os.environ.get("CHROMIUM_SDK_DATA_DIR")
LOCAL_API_PATH_OVERRIDE = (
    os.environ.get("QIYUAN_BASE_LOCAL_API_PATH")
    or os.environ.get("CHROMIUM_SDK_BASE_LOCAL_API")
    or os.environ.get("CHROMIUM_SDK_BASE_API")
)
SERVER_API_PATH = (
    os.environ.get("QIYUAN_BASE_API_PATH")
    or qiyuan_config.bundled_browser_config().get("base_api_path")
    or "http://127.0.0.1:9003"
)
LOCAL_API_PATH = (
    LOCAL_API_PATH_OVERRIDE
    or qiyuan_config.bundled_browser_config().get("base_local_api_path")
    or "http://127.0.0.1:9003"
)
if getattr(sys, "frozen", False):
    # PyInstaller stores the frontend data under the explicit ``admin`` data
    # directory in the temporary extraction root.
    STATIC_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(__file__)), "admin", "static")
else:
    STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
FRONTEND_DIST = os.path.join(STATIC_DIR, "dist")
PROCESS_ROLE = os.environ.get("QIYUAN_PROCESS_ROLE", "server").lower()
if PROCESS_ROLE not in ("server", "client"):
    raise RuntimeError("QIYUAN_PROCESS_ROLE must be server or client")

@asynccontextmanager
async def lifespan(app: FastAPI):
    log_path = configure_logging(client.data_dir)
    database = server_client.storage.db_path if server_client else "远程服务端 " + SERVER_API_PATH
    logging.getLogger(__name__).info("管理服务启动；角色: %s；数据库: %s；日志: %s", PROCESS_ROLE, database, log_path)
    print(f"管理服务启动；角色: {PROCESS_ROLE}")
    try:
        yield
    finally:
        logging.getLogger(__name__).info("管理服务停止")


app = FastAPI(title="Qiyuan SDK Admin", version="0.1.0", lifespan=lifespan)
if os.path.isdir(FRONTEND_DIST):
    app.mount("/static/dist", StaticFiles(directory=FRONTEND_DIST), name="frontend")
server_client = ChromiumClient(data_dir=DATA_DIR, base_api_path=LOCAL_API_PATH_OVERRIDE, server_role=True) if PROCESS_ROLE == "server" else None
local_client = ChromiumClient(data_dir=DATA_DIR, base_api_path=LOCAL_API_PATH_OVERRIDE, remote_api_path=SERVER_API_PATH) if PROCESS_ROLE == "client" else None
client = local_client or server_client


def _local_listener_port() -> int:
    """Use the configured API URL for the listener port."""
    endpoint = SERVER_API_PATH if PROCESS_ROLE == "server" else LOCAL_API_PATH
    try:
        port = urlparse(endpoint).port
        return int(port or 9003)
    except (TypeError, ValueError):
        return 9003


def _initialize_default_browser_dir() -> None:
    """Seed the default browser directory once, preserving any existing files."""
    target = qiyuan_config.default_qiyuan_dir()
    if os.path.normcase(client.browser_app_data_dir) != os.path.normcase(target):
        target = client.browser_app_data_dir
    for name in ("client", "config", "extends"):
        os.makedirs(os.path.join(target, name), exist_ok=True)
    config_target = qiyuan_config.ensure_qiyuan_config(
        client.local_api_path, browser_app_data_dir=target
    )
    public_key = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sdk", "keys", "rsa_public.pem"))
    public_key_target = os.path.join(target, "config", "rsa_public.pem")
    if os.path.isfile(public_key) and not os.path.exists(public_key_target):
        shutil.copy2(public_key, public_key_target)
    client.storage.set_config("default_browser_dir_initialized", "1")


if PROCESS_ROLE == "client":
    _initialize_default_browser_dir()


# Same-origin page assets; the route modules decide where they are served.
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


from admin import server_api, local_api

if server_client:
    server_api.bind_client(server_client)
server_api.bind_pages(HOME_PAGE_HTML, ERROR_PAGE_HTML, FRONTEND_DIST)
local_api.bind_pages(STATIC_DIR, FRONTEND_DIST, HOME_PAGE_HTML, ERROR_PAGE_HTML)
if PROCESS_ROLE == "server":
    app.include_router(server_api.router)
if PROCESS_ROLE == "client":
    local_api.bind_client(local_client)
    app.include_router(local_api.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0" if PROCESS_ROLE == "server" else "127.0.0.1",
        port=_local_listener_port(),
        loop="admin.event_loop:selector_loop_factory",
    )
