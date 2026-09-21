"""Chromium fingerprint browser SDK.

A self-contained Python SDK that unifies local browser control and the
(reimplemented) backend environment/proxy management into one module, backed
by SQLite.

    from sdk import ChromiumClient

    client = ChromiumClient()
    code = client.env_create(name="my-env", platform="Win32")["code"]
    client.env_open(code)
"""

from .client import ChromiumClient
from .errors import BrowserError, NotFoundError, SdkError, ValidationError
from .fingerprint import (
    build_fingerprint_json,
    build_fingerprint_payload,
    generate_fingerprint,
    generate_user_agent,
)
from .models import Environment, Fingerprint, Proxy

__version__ = "0.1.0"

__all__ = [
    "ChromiumClient",
    "SdkError",
    "NotFoundError",
    "ValidationError",
    "BrowserError",
    "Environment",
    "Fingerprint",
    "Proxy",
    "generate_fingerprint",
    "generate_user_agent",
    "build_fingerprint_json",
    "build_fingerprint_payload",
    "__version__",
]
