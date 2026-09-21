"""Windows event-loop setup for the local HTTP server."""

from __future__ import annotations

import asyncio
import sys


def configure_windows_event_loop() -> None:
    """Avoid IOCP AcceptEx failures caused by short-lived loopback clients."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    """Loop factory for Uvicorn 0.52+, which bypasses the global policy."""
    return asyncio.SelectorEventLoop()
