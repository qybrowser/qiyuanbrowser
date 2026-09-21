"""Routes hosted by the server API base URL."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
import os
from fastapi import HTTPException
from sdk import ChromiumClient
from sdk.errors import SdkError
from admin.http_utils import (ok, err, api_ok, api_err, bearer as _bearer,
                              run as _run, query_params as _qp, positive_int as _positive_int)

router = APIRouter(tags=["Server API"])
client: ChromiumClient
HOME_PAGE_HTML = ""
ERROR_PAGE_HTML = ""
FRONTEND_DIST = ""


def bind_client(instance: ChromiumClient) -> None:
    global client
    client = instance


def bind_pages(home_html: str, error_html: str, frontend_dist: str = "") -> None:
    global HOME_PAGE_HTML, ERROR_PAGE_HTML, FRONTEND_DIST
    HOME_PAGE_HTML, ERROR_PAGE_HTML = home_html, error_html
    FRONTEND_DIST = frontend_dist


@router.get("/")
def index() -> FileResponse:
    path = os.path.join(FRONTEND_DIST, "index.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=503, detail="管理界面尚未构建")
    return FileResponse(path)


@router.get("/pages/home.html", response_class=HTMLResponse)
def page_home() -> HTMLResponse:
    return HTMLResponse(HOME_PAGE_HTML)


@router.get("/pages/error.html", response_class=HTMLResponse)
def page_error() -> HTMLResponse:
    return HTMLResponse(ERROR_PAGE_HTML)


@router.get("/internal/client/environment")
def internal_environment(code: str) -> JSONResponse:
    return ok(client.storage.get_environment(code))


@router.get("/internal/client/environments")
def internal_environments(page: int = 1, page_size: int = 1000000, keyword: str = "") -> JSONResponse:
    items, total = client.storage.list_environments(page, page_size, keyword)
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/internal/client/environment/update")
async def internal_environment_update(request: Request) -> JSONResponse:
    return await _run(lambda b: client.storage.update_environment(b.get("code", ""), b.get("fields") or {}), request)


@router.get("/internal/client/proxy")
def internal_proxy(code: str) -> JSONResponse:
    return ok(client.storage.get_proxy(code))


@router.get("/internal/client/error")
def internal_error(code: str) -> JSONResponse:
    return ok(client.storage.get_error(code))


@router.post("/internal/client/proxy/update")
async def internal_proxy_update(request: Request) -> JSONResponse:
    return await _run(lambda b: client.storage.update_proxy(b.get("code", ""), b.get("fields") or {}), request)


@router.post("/internal/client/runtime")
async def internal_runtime(request: Request) -> JSONResponse:
    return await _run(lambda b: client.storage.set_runtime(b.get("code", ""), b.get("pid"), b.get("debug_port")), request)


@router.get("/internal/client/token")
def internal_token() -> JSONResponse:
    return ok(client.token)


@router.get("/internal/client/extensions")
def internal_extensions(code: str) -> JSONResponse:
    return ok(client.storage.list_environment_extensions(code))


@router.post("/internal/client/extensions/sync-state")
async def internal_extension_sync_state(request: Request) -> JSONResponse:
    return await _run(lambda b: client.storage.upsert_extension_sync(b.get("environment_code", ""), b.get("extension_code", ""), b.get("fields") or {}), request)


@router.get("/internal/client/extensions/download/{code}")
def internal_extension_download(code: str) -> FileResponse:
    extension = client.storage.get_extension(code)
    if not extension:
        raise HTTPException(status_code=404, detail="扩展不存在")
    try:
        source = client.extensions._source_zip(extension)
    except SdkError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(source, media_type="application/zip", filename=f"{code}.zip")


async def _extension_payload(request: Request):
    form = await request.form()
    data = {key: form.get(key) for key in ("code", "name", "version", "browser_kernel", "extension_type", "provider", "source_url", "description", "status", "bind_all", "environment_codes") if form.get(key) is not None}
    raw = data.get("environment_codes")
    if isinstance(raw, str):
        try:
            import json
            parsed = json.loads(raw)
            data["environment_codes"] = parsed if isinstance(parsed, list) else [raw]
        except Exception:
            data["environment_codes"] = [x.strip() for x in raw.split(",") if x.strip()]
    upload = form.get("file")
    return data, upload


@router.get("/open/extension/list")
def extension_list(request: Request) -> JSONResponse:
    q = _qp(request)
    try:
        return ok(client.extension_list(page=_positive_int(q.get("page"), 1), page_size=_positive_int(q.get("page_size"), 20), keyword=q.get("keyword", ""), kernel=q.get("browser_kernel", ""), extension_type=q.get("extension_type", "")))
    except SdkError as exc:
        return err(str(exc))


@router.get("/open/extension/detail")
def extension_detail(request: Request) -> JSONResponse:
    try:
        return ok(client.extension_detail(_qp(request).get("code", "")))
    except SdkError as exc:
        return err(str(exc))


@router.post("/open/extension/create")
async def extension_create(request: Request) -> JSONResponse:
    try:
        data, upload = await _extension_payload(request)
        return ok(client.extension_create(data, upload))
    except SdkError as exc:
        return err(str(exc))
    except Exception as exc:
        return err(f"扩展保存失败: {exc}")


@router.post("/open/extension/update")
async def extension_update(request: Request) -> JSONResponse:
    try:
        data, upload = await _extension_payload(request)
        code = str(data.pop("code", ""))
        return ok(client.extension_update(code, data, upload))
    except SdkError as exc:
        return err(str(exc))
    except Exception as exc:
        return err(f"扩展保存失败: {exc}")


@router.post("/open/extension/delete")
async def extension_delete(request: Request) -> JSONResponse:
    return await _run(lambda b: client.extension_delete(str(b.get("code", ""))), request)


@router.post("/open/extension/bindings")
async def extension_bindings(request: Request) -> JSONResponse:
    return await _run(lambda b: client.extension_bindings(str(b.get("code", "")), b.get("environment_codes") or (["*"] if b.get("bind_all") else [])), request)


@router.get("/api/v1/browser/home-data/{md5}")
def browser_home_data(md5: str) -> JSONResponse:
    try:
        return api_ok(client.browser_home_data(md5))
    except SdkError as exc:
        return api_err(str(exc), code=404)


@router.get("/api/check-network")
def check_network() -> JSONResponse:
    """Direct IP geo lookup used by the browser start page."""
    return JSONResponse(client.ip_geo(""))


@router.post("/api/check-proxy")
async def check_proxy(request: Request) -> JSONResponse:
    """Proxy IP geo lookup used by the browser start page."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    return JSONResponse(client.check_proxy(body))


@router.get("/api/v1/browser/error-data/{code}")
def browser_error_data(code: str) -> JSONResponse:
    return api_ok(client.browser_error_data(code))


@router.get("/open/env/list")
def env_list(request: Request) -> JSONResponse:
    q = _qp(request)
    try:
        return ok(client.env_list(
            page=_positive_int(q.get("page"), 1),
            page_size=_positive_int(q.get("page_size"), 20),
            keyword=q.get("keyword", ""),
        ))
    except SdkError as exc:
        return err(str(exc))


@router.get("/open/env/detail")
def env_detail(request: Request) -> JSONResponse:
    code = _qp(request).get("code", "")
    try:
        return ok(client.env_detail(code))
    except SdkError as exc:
        return err(str(exc))


@router.post("/open/env/create")
async def env_create(request: Request) -> JSONResponse:
    return await _run(lambda b: client.env_create(**b), request)


@router.post("/open/env/update")
async def env_update(request: Request) -> JSONResponse:
    return await _run(lambda b: (client.env_update(b.pop("code", ""), **b), None)[1], request)


@router.post("/open/env/delete")
async def env_delete(request: Request) -> JSONResponse:
    return await _run(lambda b: (client.env_delete(b.get("code", "")), None)[1], request)


@router.post("/open/env/randomize_fingerprint")
async def env_randomize(request: Request) -> JSONResponse:
    return await _run(
        lambda b: client.env_randomize_fingerprint(b.get("code", "")), request
    )


@router.get("/open/proxy/list")
def proxy_list(request: Request) -> JSONResponse:
    q = _qp(request)
    try:
        return ok(client.proxy_list(
            page=_positive_int(q.get("page"), 1),
            page_size=_positive_int(q.get("page_size"), 20),
            keyword=q.get("keyword", ""),
        ))
    except SdkError as exc:
        return err(str(exc))


@router.get("/open/proxy/detail")
def proxy_detail(request: Request) -> JSONResponse:
    try:
        return ok(client.proxy_detail(_qp(request).get("code", "")))
    except SdkError as exc:
        return err(str(exc))


@router.post("/open/proxy/create")
async def proxy_create(request: Request) -> JSONResponse:
    return await _run(lambda b: client.proxy_create(**b), request)


@router.post("/open/proxy/update")
async def proxy_update(request: Request) -> JSONResponse:
    return await _run(lambda b: (client.proxy_update(b.pop("code", ""), **b), None)[1], request)


@router.post("/open/proxy/delete")
async def proxy_delete(request: Request) -> JSONResponse:
    return await _run(lambda b: (client.proxy_delete(b.get("code", "")), None)[1], request)


@router.get("/api/v1/browser/md5/{uuid}")
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


@router.post("/api/v1/browser/error/report")
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


@router.post("/api/v1/client/browser/tabs")
async def client_browser_tabs(request: Request) -> JSONResponse:
    """标签上报。过滤内部/无效链接，按域名去重并最多保存 5 条。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    result = client.update_tabs(body.get("md5", ""), body.get("tabs", ""))
    return api_ok(result)


@router.post("/api/browser/status")
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

