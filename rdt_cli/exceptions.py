"""Custom exceptions for Reddit CLI API client."""

from __future__ import annotations

from typing import Any


class RedditApiError(Exception):
    """Base exception for Reddit API errors."""

    def __init__(self, message: str, code: int | str | None = None, response: dict | None = None):
        super().__init__(message)
        self.code = code
        self.response = response


class SessionExpiredError(RedditApiError):
    """Raised when session cookies have expired."""

    def __init__(self):
        super().__init__(
            "Session expired. Please re-login: rdt logout && rdt login",
            code=401,
        )


class AuthRequiredError(RedditApiError):
    """Raised when user is not logged in."""

    def __init__(self):
        super().__init__("Not logged in. Use 'rdt login' to authenticate")


class RateLimitError(RedditApiError):
    """Raised when Reddit rate-limits the request."""

    def __init__(self, retry_after: float | None = None):
        msg = "Rate limited by Reddit"
        if retry_after:
            msg += f" (retry after {retry_after:.0f}s)"
        super().__init__(msg, code=429)
        self.retry_after = retry_after


class NotFoundError(RedditApiError):
    """Raised when a subreddit, user, or post is not found."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", code=404)


class ForbiddenError(RedditApiError):
    """Raised when access is forbidden (private subreddit, etc.)."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(f"Access forbidden: {resource}", code=403)


def error_code_for_exception(exc: Exception) -> str:
    """Map domain exceptions to stable error code strings."""
    if isinstance(exc, (AuthRequiredError, SessionExpiredError)):
        return "not_authenticated"
    if isinstance(exc, RateLimitError):
        return "rate_limited"
    if isinstance(exc, NotFoundError):
        return "not_found"
    if isinstance(exc, ForbiddenError):
        return "forbidden"
    if isinstance(exc, RedditApiError):
        return "api_error"
    return "unknown_error"
