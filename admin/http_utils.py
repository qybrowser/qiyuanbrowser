"""Response envelopes and request parsing shared by local and server routes."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from sdk.errors import SdkError

_NO_DATA = object()


def ok(data: Any = _NO_DATA) -> JSONResponse:
    payload = {"success": True}
    if data is not _NO_DATA:
        payload["data"] = data
    return JSONResponse(payload)


def err(message: str) -> JSONResponse:
    return JSONResponse({"success": False, "error": message})


def api_ok(data: Any = None, message: str = "OK") -> JSONResponse:
    return JSONResponse({"code": 200, "message": message, "data": data, "success": True})


def api_err(message: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"code": code, "message": message, "data": None, "success": False})


def bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    return auth[7:] if auth.startswith("Bearer ") else None


async def run(handler: Callable[[Dict[str, Any]], Any], request: Request) -> JSONResponse:
    try:
        body = await request.json() if await request.body() else {}
    except Exception:
        body = {}
    try:
        # Browser startup callbacks need this event loop while opening waits.
        result = await run_in_threadpool(handler, body or {})
        return ok() if result is None else ok(result)
    except SdkError as exc:
        return err(str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logging.getLogger(__name__).exception("请求处理失败")
        return err(f"内部错误: {exc}")


def query_params(request: Request) -> Dict[str, str]:
    return dict(request.query_params)


def positive_int(value: Any, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback
