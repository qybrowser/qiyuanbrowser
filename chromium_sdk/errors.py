"""Exception hierarchy for the Chromium fingerprint SDK."""


class SdkError(Exception):
    """Base class for all SDK errors."""


class NotFoundError(SdkError):
    """Requested environment / proxy does not exist."""


class ValidationError(SdkError):
    """Missing or invalid parameters."""


class BrowserError(SdkError):
    """Failure while launching / closing the local browser."""
