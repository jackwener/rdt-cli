"""API client for Reddit with rate limiting, retry, and anti-detection."""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any

import httpx

from .constants import (
    ALL_URL,
    BASE_URL,
    COMMENT_URL,
    DEFAULT_LIMIT,
    HEADERS,
    HOME_URL,
    ME_URL,
    OAUTH_URL,
    POPULAR_URL,
    POST_COMMENTS_SHORT_URL,
    POST_COMMENTS_URL,
    SAVE_URL,
    SEARCH_URL,
    SUBREDDIT_ABOUT_URL,
    SUBREDDIT_SEARCH_URL,
    SUBREDDIT_URL,
    SUBSCRIBE_URL,
    UNSAVE_URL,
    USER_ABOUT_URL,
    USER_COMMENTS_URL,
    USER_POSTS_URL,
    USER_SAVED_URL,
    VOTE_URL,
)
from .exceptions import (
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    RedditApiError,
    SessionExpiredError,
)

logger = logging.getLogger(__name__)


class RedditClient:
    """Reddit API client with Gaussian jitter, exponential backoff, and session-stable identity.

    Anti-detection strategy:
    - Gaussian jitter delay between requests
    - 5% chance of random long pause (2-5s) to mimic reading
    - Exponential backoff on HTTP 429/5xx (up to 3 retries)
    - Response cookies merged back into session jar
    - Per-request logging with counter
    """

    def __init__(
        self,
        credential: object | None = None,
        timeout: float = 30.0,
        request_delay: float = 1.0,
        max_retries: int = 3,
    ):
        self.credential = credential
        self._timeout = timeout
        self._request_delay = request_delay
        self._max_retries = max_retries
        self._last_request_time = 0.0
        self._request_count = 0
        self._http: httpx.Client | None = None

    def _build_client(self) -> httpx.Client:
        cookies = {}
        if self.credential:
            cookies = self.credential.cookies
        return httpx.Client(
            base_url=BASE_URL,
            headers=dict(HEADERS),
            cookies=cookies,
            follow_redirects=True,
            timeout=httpx.Timeout(self._timeout),
        )

    @property
    def client(self) -> httpx.Client:
        if not self._http:
            raise RuntimeError("Client not initialized. Use 'with RedditClient() as client:'")
        return self._http

    def __enter__(self) -> RedditClient:
        self._http = self._build_client()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._http:
            self._http.close()
            self._http = None

    @property
    def request_stats(self) -> dict[str, int]:
        return {"request_count": self._request_count}

    # ── Rate limiting ───────────────────────────────────────────────

    def _rate_limit_delay(self) -> None:
        """Enforce minimum delay with Gaussian jitter to mimic human browsing."""
        if self._request_delay <= 0:
            return
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            jitter = max(0, random.gauss(0.3, 0.15))
            if random.random() < 0.05:
                jitter += random.uniform(2.0, 5.0)
            time.sleep(self._request_delay - elapsed + jitter)

    # ── Response cookies ────────────────────────────────────────────

    def _merge_response_cookies(self, resp: httpx.Response) -> None:
        """Merge Set-Cookie headers back into session jar."""
        for name, value in resp.cookies.items():
            if value:
                self.client.cookies.set(name, value)

    # ── Core request ────────────────────────────────────────────────

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Rate-limited request with retry and cookie merge."""
        self._rate_limit_delay()

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            t0 = time.time()
            try:
                resp = self.client.request(method, url, **kwargs)
                elapsed = time.time() - t0
                self._merge_response_cookies(resp)
                self._request_count += 1
                self._last_request_time = time.time()
                logger.info(
                    "[#%d] %s %s → %d (%.2fs)",
                    self._request_count,
                    method,
                    url[:80],
                    resp.status_code,
                    elapsed,
                )

                # Retry on server errors
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 5))
                    logger.warning("Rate limited, waiting %.1fs", retry_after)
                    time.sleep(retry_after)
                    continue

                if resp.status_code in (500, 502, 503, 504):
                    wait = (2**attempt) + random.uniform(0, 1)
                    logger.warning("HTTP %d, retrying in %.1fs", resp.status_code, wait)
                    time.sleep(wait)
                    continue

                # Client errors
                if resp.status_code == 401:
                    raise SessionExpiredError()
                if resp.status_code == 403:
                    raise ForbiddenError()
                if resp.status_code == 404:
                    raise NotFoundError()

                resp.raise_for_status()

                # Reddit returns HTML on some error pages
                text = resp.text
                if text.strip().startswith("<"):
                    raise RedditApiError("Received HTML instead of JSON (possible auth redirect)")

                return resp.json()

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                wait = (2**attempt) + random.uniform(0, 1)
                logger.warning("Network error: %s, retrying in %.1fs", exc, wait)
                time.sleep(wait)

        if last_exc:
            raise RedditApiError(f"Request failed after {self._max_retries} retries: {last_exc}") from last_exc
        raise RedditApiError(f"Request failed after {self._max_retries} retries")

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET request."""
        return self._request("GET", url, params=params)

    def _post(self, url: str, data: dict[str, Any] | None = None) -> Any:
        """POST request."""
        return self._request("POST", url, data=data)

    # ── Listing helpers ─────────────────────────────────────────────

    @staticmethod
    def _extract_posts(data: dict) -> list[dict]:
        """Extract post list from Reddit Listing response."""
        if isinstance(data, list):
            # Comments endpoint returns [post_listing, comments_listing]
            return data
        children = data.get("data", {}).get("children", [])
        return [child.get("data", child) for child in children]

    @staticmethod
    def _extract_after(data: dict) -> str | None:
        """Extract pagination cursor."""
        if isinstance(data, list):
            return None
        return data.get("data", {}).get("after")

    # ── Feed / Listing endpoints ────────────────────────────────────

    def get_home(self, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get home feed (requires login)."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(HOME_URL, params=params)

    def get_popular(self, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get /r/popular."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(POPULAR_URL, params=params)

    def get_all(self, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get /r/all."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(ALL_URL, params=params)

    def get_subreddit(
        self,
        subreddit: str,
        sort: str = "hot",
        limit: int = DEFAULT_LIMIT,
        after: str | None = None,
        time_filter: str | None = None,
    ) -> dict:
        """Get subreddit listing."""
        url = f"/r/{subreddit}.json" if sort == "hot" else f"/r/{subreddit}/{sort}.json"
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        if time_filter and sort in ("top", "controversial"):
            params["t"] = time_filter
        return self._get(url, params=params)

    def get_subreddit_about(self, subreddit: str) -> dict:
        """Get subreddit info."""
        data = self._get(SUBREDDIT_ABOUT_URL.format(subreddit=subreddit), params={"raw_json": 1})
        return data.get("data", data)

    # ── Post / Comments ─────────────────────────────────────────────

    def get_post_comments(
        self,
        post_id: str,
        subreddit: str | None = None,
        sort: str = "best",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict]:
        """Get post and its comments.

        Returns [post_listing, comments_listing].
        """
        if subreddit:
            url = POST_COMMENTS_URL.format(subreddit=subreddit, post_id=post_id)
        else:
            url = POST_COMMENTS_SHORT_URL.format(post_id=post_id)
        params: dict[str, Any] = {"sort": sort, "limit": limit, "raw_json": 1}
        return self._get(url, params=params)

    # ── Search ──────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        subreddit: str | None = None,
        sort: str = "relevance",
        time_filter: str = "all",
        limit: int = DEFAULT_LIMIT,
        after: str | None = None,
    ) -> dict:
        """Search posts."""
        if subreddit:
            url = SUBREDDIT_SEARCH_URL.format(subreddit=subreddit)
        else:
            url = SEARCH_URL
        params: dict[str, Any] = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": limit,
            "restrict_sr": "on" if subreddit else "off",
            "raw_json": 1,
        }
        if after:
            params["after"] = after
        return self._get(url, params=params)

    # ── User ────────────────────────────────────────────────────────

    def get_user_about(self, username: str) -> dict:
        """Get user profile info."""
        data = self._get(USER_ABOUT_URL.format(username=username), params={"raw_json": 1})
        return data.get("data", data)

    def get_user_posts(self, username: str, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get user's submitted posts."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(USER_POSTS_URL.format(username=username), params=params)

    def get_user_comments(self, username: str, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get user's comments."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(USER_COMMENTS_URL.format(username=username), params=params)

    # ── Identity (requires auth) ────────────────────────────────────

    def get_me(self) -> dict:
        """Get current user info. Uses oauth.reddit.com."""
        # For the .json API, we try /api/v1/me or fallback to username based
        try:
            return self._get("/api/me.json", params={"raw_json": 1})
        except RedditApiError:
            # Fallback: try to get identity from cookie-based session
            return {"error": "Identity endpoint requires OAuth token"}

    # ── Write actions (require authentication) ──────────────────────

    def vote(self, fullname: str, direction: int) -> dict:
        """Vote on a post or comment. direction: 1=upvote, 0=unvote, -1=downvote."""
        return self._post(VOTE_URL, data={"id": fullname, "dir": str(direction)})

    def save_item(self, fullname: str) -> dict:
        """Save a post or comment."""
        return self._post(SAVE_URL, data={"id": fullname})

    def unsave_item(self, fullname: str) -> dict:
        """Unsave a post or comment."""
        return self._post(UNSAVE_URL, data={"id": fullname})

    def subscribe(self, subreddit: str, action: str = "sub") -> dict:
        """Subscribe or unsubscribe. action: 'sub' or 'unsub'."""
        return self._post(SUBSCRIBE_URL, data={"sr_name": subreddit, "action": action})

    def post_comment(self, parent_fullname: str, text: str) -> dict:
        """Post a comment."""
        return self._post(COMMENT_URL, data={"parent": parent_fullname, "text": text})
