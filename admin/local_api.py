"""Routes hosted by the local API base URL."""

from __future__ import annotations

import os
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen
from sdk import ChromiumClient
from sdk.errors import SdkError
from sdk.gpu_fingerprint import get_gpu_options
from admin.http_utils import (ok, err, api_ok, api_err, bearer as _bearer,
                              run as _run, query_params as _qp)

router = APIRouter(tags=["Local API"])
client: ChromiumClient


def bind_client(instance: ChromiumClient) -> None:
    global client
    client = instance


STATIC_DIR = ""
FRONTEND_DIST = ""
HOME_PAGE_HTML = ""
ERROR_PAGE_HTML = ""


@router.get("/")
def index() -> FileResponse:
    """Expose the management UI in client mode as well."""
    path = os.path.join(FRONTEND_DIST, "index.html")
    if not os.path.isfile(path):
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="管理界面尚未构建")
    return FileResponse(path)


def bind_pages(static_dir: str, frontend_dist: str, home_html: str, error_html: str) -> None:
    global STATIC_DIR, FRONTEND_DIST, HOME_PAGE_HTML, ERROR_PAGE_HTML
    STATIC_DIR, FRONTEND_DIST = static_dir, frontend_dist
    HOME_PAGE_HTML, ERROR_PAGE_HTML = home_html, error_html


@router.get("/open/settings/capabilities")
def settings_capabilities() -> JSONResponse:
    return ok({"process_role": "client", "local_settings": True, "kernel_management": True, "token_update": True})


@router.get("/open/settings/browser")
def browser_settings() -> JSONResponse:
    return ok(client.browser_settings())


@router.get("/open/settings/kernels")
def browser_kernels() -> JSONResponse:
    from sdk import qiyuan_config
    return ok(qiyuan_config.inspect_qiyuan_dir(client.browser_app_data_dir)["kernels"])


@router.post("/open/settings/browser")
async def browser_settings_save(request: Request) -> JSONResponse:
    return await _run(
        lambda b: client.set_browser_app_data_dir(b.get("browser_app_data_dir")),
        request,
    )


@router.post("/open/settings/token")
async def browser_token_save(request: Request) -> JSONResponse:
    return await _run(lambda b: client.update_token(b.get("token", "")), request)


@router.get("/open/settings/token")
def browser_token_get() -> JSONResponse:
    """Return the configured token so the local settings page can initialize it."""
    try:
        return ok({"token": client.current_token()})
    except SdkError as exc:
        return err(str(exc))


@router.post("/open/settings/kernels/upload")
async def kernel_upload(request: Request) -> JSONResponse:
    try:
        form = await request.form()
        kernel = str(form.get("kernel") or "")
        version = str(form.get("version") or "")
        set_default = str(form.get("set_default") or "false").lower() in ("1", "true", "yes", "on")
        upload = form.get("file")
        if upload is None or not hasattr(upload, "file"):
            raise SdkError("请选择内核 ZIP 文件")
        return ok(client.install_kernel(kernel, version, upload, set_default))
    except SdkError as exc:
        return err(str(exc))
    except Exception as exc:
        return err(f"内核安装失败: {exc}")


@router.get("/api/browser-home-data")
def firefox_browser_home_data(md5: str = "") -> JSONResponse:
    """Firefox's bundled start-page extension uses the local Electron path."""
    try:
        return api_ok(client.browser_home_data(md5))
    except SdkError as exc:
        return api_err(str(exc), code=404)


@router.get("/api/browser-error-data")
def firefox_browser_error_data(code: str = "") -> JSONResponse:
    return api_ok(client.browser_error_data(code))


@router.post("/api/update-proxy-ip")
async def firefox_update_proxy_ip(request: Request) -> JSONResponse:
    """Acknowledge the Firefox start-page geo callback (no IP field in local DB)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    return JSONResponse({"success": bool(body.get("md5"))})


@router.get("/api/check-network")
def check_network() -> JSONResponse:
    """Direct (no-proxy) IP geo for the start page. No auth."""
    return JSONResponse(client.ip_geo(""))


@router.post("/open/env/open")
async def env_open(request: Request) -> JSONResponse:
    return await _run(
        lambda b: client.env_open(
            b.get("code", ""), args=b.get("args"),
            headless=b.get("headless") is True,
            open_tabs=b.get("openTabs") is True,
            need_debug_port=b.get("needDebugPort") is not False,
        ), request
    )


@router.post("/open/env/close")
async def env_close(request: Request) -> JSONResponse:
    return await _run(lambda b: (client.env_close(b.get("code", "")), None)[1], request)


@router.get("/open/env/status")
def env_status(request: Request) -> JSONResponse:
    code = _qp(request).get("code", "")
    try:
        return ok(client.env_status(code))
    except SdkError as exc:
        return err(str(exc))


@router.post("/open/env/clear_cache")
async def env_clear_cache(request: Request) -> JSONResponse:
    return await _run(lambda b: (client.env_clear_cache(b.get("code", "")), None)[1], request)


@router.post("/open/extension/sync")
async def extension_sync(request: Request) -> JSONResponse:
    return await _run(lambda b: client.extensions.sync(client._require_env(str(b.get("code", "")))), request)


@router.post("/open/proxy/check")
async def proxy_check(request: Request) -> JSONResponse:
    return await _run(client.proxy_check, request)


@router.post("/open/fingerprint/draft")
async def fingerprint_draft(request: Request) -> JSONResponse:
    from sdk.fingerprint import generate_fingerprint
    return await _run(lambda b: generate_fingerprint(b.get("platform", "Win32")), request)


@router.get("/open/gpu-options")
def open_gpu_options() -> JSONResponse:
    return ok(get_gpu_options())


@router.get("/api/v1/browser/gpu-options")
def browser_gpu_options() -> JSONResponse:
    """Same payload as backend GET /api/v1/browser/gpu-options."""
    return api_ok(get_gpu_options())


@router.post("/api/check-proxy")
async def check_proxy(request: Request) -> JSONResponse:
    """代理检测。body {proxy_type, proxy_addr, proxy_port, username, password}"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    return JSONResponse(client.check_proxy(body))


@router.get("/api/ip-geo")
def ip_geo(request: Request, ip: str = "") -> JSONResponse:
    """IP 地理。Bearer 鉴权。"""
    if not client.verify_token(_bearer(request)):
        return JSONResponse({"success": False, "error": "unauthorized"})
    return JSONResponse(client.ip_geo(ip))


@router.api_route("/open/{resource}/{operation}", methods=["GET", "POST"])
async def forward_management_api(resource: str, operation: str, request: Request) -> Response:
    """Forward server-owned management APIs when the UI is opened locally.

    The client process never reads shared SQLite directly.  This fallback keeps
    the browser UI same-origin while sending environment/proxy/extension CRUD
    requests to the configured server API.  More specific local routes above
    (open, close, settings, proxy check, etc.) take precedence.
    """
    if not client.remote_api_path:
        return JSONResponse({"success": False, "error": "服务端接口未配置"}, status_code=404)
    query = request.url.query
    path = f"/open/{resource}/{operation}"
    url = client.remote_api_path + path + (f"?{query}" if query else "")
    body = await request.body()
    headers = {}
    for name in ("content-type", "authorization"):
        value = request.headers.get(name)
        if value:
            headers[name] = value
    try:
        with urlopen(UrlRequest(url, data=body or None, headers=headers, method=request.method), timeout=30) as upstream:
            payload = upstream.read()
            content_type = upstream.headers.get("content-type", "application/json").split(";", 1)[0]
            return Response(content=payload, status_code=upstream.status, media_type=content_type)
    except HTTPError as exc:
        payload = exc.read()
        return Response(content=payload, status_code=exc.code, media_type="application/json")
    except URLError as exc:
        return JSONResponse({"success": False, "error": f"服务端不可用: {exc.reason}"}, status_code=502)

