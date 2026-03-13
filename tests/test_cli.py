"""Unit tests for rdt-cli — mocked, no network required."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from rdt_cli import __version__
from rdt_cli.cli import cli

runner = CliRunner()


# ── CLI basic ───────────────────────────────────────────────────────


class TestCliBasic:
    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "rdt" in result.output

    def test_all_commands_registered(self):
        result = runner.invoke(cli, ["--help"])
        expected = [
            "login", "logout", "status",
            "feed", "popular", "sub", "sub-info", "user", "user-posts",
            "read", "show",
            "search", "export",
            "upvote", "save", "subscribe",
        ]
        for cmd in expected:
            assert cmd in result.output, f"Missing command: {cmd}"

    def test_verbose_flag(self):
        result = runner.invoke(cli, ["-v", "--help"])
        assert result.exit_code == 0


# ── Command help ────────────────────────────────────────────────────


class TestCommandHelp:
    """Every command's --help should work without error."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "login", "logout", "status",
            "feed", "popular", "sub", "sub-info", "user", "user-posts",
            "read", "show",
            "search", "export",
            "upvote", "save", "subscribe",
        ],
    )
    def test_help(self, cmd):
        result = runner.invoke(cli, [cmd, "--help"])
        assert result.exit_code == 0, f"{cmd} --help failed: {result.output}"


# ── Auth commands (mocked) ──────────────────────────────────────────


class TestAuthCommands:
    def test_status_not_authenticated(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            result = runner.invoke(cli, ["status"])
            assert result.exit_code == 0
            assert "Not authenticated" in result.output or "⚠" in result.output

    def test_status_json_not_authenticated(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            result = runner.invoke(cli, ["status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["authenticated"] is False

    def test_login_already_authenticated(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={"reddit_session": "test"})
        with patch("rdt_cli.auth.get_credential", return_value=cred):
            result = runner.invoke(cli, ["login"])
            assert result.exit_code == 0
            assert "Already" in result.output or "✅" in result.output

    def test_logout(self):
        with patch("rdt_cli.auth.clear_credential") as mock_clear:
            result = runner.invoke(cli, ["logout"])
            assert result.exit_code == 0
            assert "✅" in result.output
            mock_clear.assert_called_once()


# ── Constants ───────────────────────────────────────────────────────


class TestConstants:
    def test_base_url(self):
        from rdt_cli.constants import BASE_URL
        assert "reddit.com" in BASE_URL

    def test_headers_complete(self):
        from rdt_cli.constants import HEADERS
        assert "User-Agent" in HEADERS
        assert "sec-ch-ua" in HEADERS
        assert "Chrome/133" in HEADERS["User-Agent"]

    def test_sort_options(self):
        from rdt_cli.constants import SORT_OPTIONS, TIME_FILTERS
        assert "hot" in SORT_OPTIONS
        assert "new" in SORT_OPTIONS
        assert "top" in SORT_OPTIONS
        assert "week" in TIME_FILTERS
        assert "all" in TIME_FILTERS

    def test_required_cookies(self):
        from rdt_cli.constants import REQUIRED_COOKIES
        assert "reddit_session" in REQUIRED_COOKIES


# ── Credential ──────────────────────────────────────────────────────


class TestCredential:
    def test_from_dict(self):
        from rdt_cli.auth import Credential
        cred = Credential.from_dict({"cookies": {"reddit_session": "abc"}})
        assert cred.is_valid
        assert cred.cookies["reddit_session"] == "abc"

    def test_to_dict(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={"k": "v"})
        data = cred.to_dict()
        assert "cookies" in data
        assert "saved_at" in data

    def test_empty_credential(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={})
        assert not cred.is_valid

    def test_as_cookie_header(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={"a": "1", "b": "2"})
        header = cred.as_cookie_header()
        assert "a=1" in header
        assert "b=2" in header


# ── Exceptions ──────────────────────────────────────────────────────


class TestExceptions:
    def test_hierarchy(self):
        from rdt_cli.exceptions import (
            AuthRequiredError,
            ForbiddenError,
            NotFoundError,
            RateLimitError,
            RedditApiError,
            SessionExpiredError,
        )
        assert issubclass(SessionExpiredError, RedditApiError)
        assert issubclass(AuthRequiredError, RedditApiError)
        assert issubclass(RateLimitError, RedditApiError)
        assert issubclass(NotFoundError, RedditApiError)
        assert issubclass(ForbiddenError, RedditApiError)

    def test_error_codes(self):
        from rdt_cli.exceptions import (
            AuthRequiredError,
            NotFoundError,
            RateLimitError,
            error_code_for_exception,
        )
        assert error_code_for_exception(AuthRequiredError()) == "not_authenticated"
        assert error_code_for_exception(RateLimitError()) == "rate_limited"
        assert error_code_for_exception(NotFoundError()) == "not_found"
        assert error_code_for_exception(ValueError()) == "unknown_error"


# ── Client ──────────────────────────────────────────────────────────


class TestClient:
    def test_context_manager(self):
        from rdt_cli.auth import Credential
        from rdt_cli.client import RedditClient
        cred = Credential(cookies={})
        with RedditClient(cred) as client:
            assert client.client is not None

    def test_request_stats(self):
        from rdt_cli.auth import Credential
        from rdt_cli.client import RedditClient
        cred = Credential(cookies={})
        with RedditClient(cred) as client:
            stats = client.request_stats
            assert stats["request_count"] == 0

    def test_extract_posts(self):
        from rdt_cli.client import RedditClient
        data = {
            "data": {
                "children": [
                    {"data": {"id": "abc", "title": "Test"}},
                    {"data": {"id": "def", "title": "Test2"}},
                ],
                "after": "t3_xyz",
            }
        }
        posts = RedditClient._extract_posts(data)
        assert len(posts) == 2
        assert posts[0]["id"] == "abc"

    def test_extract_after(self):
        from rdt_cli.client import RedditClient
        data = {"data": {"after": "t3_next", "children": []}}
        assert RedditClient._extract_after(data) == "t3_next"
        assert RedditClient._extract_after({"data": {"after": None}}) is None


# ── Index Cache ─────────────────────────────────────────────────────


class TestIndexCache:
    def test_save_and_get(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        items = [
            {"id": "abc", "name": "t3_abc", "title": "Test Post", "subreddit": "python"},
            {"id": "def", "name": "t3_def", "title": "Test Post 2", "subreddit": "rust"},
        ]
        index_cache.save_index(items, source="test")

        item = index_cache.get_item_by_index(1)
        assert item is not None
        assert item["id"] == "abc"

        item2 = index_cache.get_item_by_index(2)
        assert item2["id"] == "def"

    def test_get_out_of_range(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        items = [{"id": "abc", "title": "Test"}]
        index_cache.save_index(items)

        assert index_cache.get_item_by_index(99) is None

    def test_get_index_zero(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        assert index_cache.get_item_by_index(0) is None

    def test_get_no_cache_file(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "nonexistent.json")
        assert index_cache.get_item_by_index(1) is None

    def test_get_index_info(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        index_cache.save_index(items, source="test_search")

        info = index_cache.get_index_info()
        assert info["exists"] is True
        assert info["count"] == 3
        assert info["source"] == "test_search"

    def test_index_info_no_file(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "none.json")

        info = index_cache.get_index_info()
        assert info["exists"] is False


# ── Show command ────────────────────────────────────────────────────


class TestShowCommand:
    def test_show_no_cache(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "none.json")
        result = runner.invoke(cli, ["show", "1"])
        assert result.exit_code == 0
        assert "No cached" in result.output or "cache" in result.output.lower()

    def test_show_requires_int(self):
        result = runner.invoke(cli, ["show", "abc"])
        assert result.exit_code != 0  # Click will reject non-integer


# ── Social command helpers ──────────────────────────────────────────


class TestResolveFullname:
    def test_fullname_passthrough(self):
        from rdt_cli.commands.social import _resolve_fullname
        assert _resolve_fullname("t3_abc123") == "t3_abc123"
        assert _resolve_fullname("t1_xyz") == "t1_xyz"

    def test_bare_id(self):
        from rdt_cli.commands.social import _resolve_fullname
        assert _resolve_fullname("abc123") == "t3_abc123"

    def test_index_no_cache(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "none.json")
        from rdt_cli.commands.social import _resolve_fullname
        assert _resolve_fullname("3") is None

    def test_index_with_cache(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)
        index_cache.save_index([
            {"id": "aaa", "name": "t3_aaa", "title": "First"},
            {"id": "bbb", "name": "t3_bbb", "title": "Second"},
        ])
        from rdt_cli.commands.social import _resolve_fullname
        assert _resolve_fullname("2") == "t3_bbb"
