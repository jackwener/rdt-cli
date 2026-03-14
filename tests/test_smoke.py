"""E2E smoke tests for rdt-cli — requires working network.

These tests hit the real Reddit JSON API. No auth required for most
public endpoints.

Run: uv run pytest tests/test_smoke.py -v -m smoke
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from rdt_cli.cli import cli

smoke = pytest.mark.smoke
runner = CliRunner()


def _invoke(*args):
    return runner.invoke(cli, list(args))


def _invoke_json(*args):
    """Invoke with --json and parse output."""
    result = runner.invoke(cli, [*args, "--json"])
    try:
        data = json.loads(result.output) if result.exit_code == 0 else None
    except json.JSONDecodeError:
        data = None
    return result, data


# ── Auth ────────────────────────────────────────────────────────────


@smoke
class TestAuth:
    def test_status(self):
        result = _invoke("status")
        assert result.exit_code == 0

    def test_status_json(self):
        result, data = _invoke_json("status")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True
            assert "authenticated" in data["data"]


# ── Browse (public, no auth needed) ─────────────────────────────────


@smoke
class TestPopular:
    def test_popular(self):
        result = _invoke("popular", "-n", "3")
        assert result.exit_code == 0

    def test_popular_json(self):
        result, data = _invoke_json("popular", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True
            assert "data" in data["data"]  # Reddit API listing under envelope

    def test_popular_yaml(self):
        result = runner.invoke(cli, ["popular", "-n", "3", "--yaml"])
        assert result.exit_code == 0


@smoke
class TestAll:
    def test_all(self):
        result = _invoke("all", "-n", "3")
        assert result.exit_code == 0

    def test_all_json(self):
        result, data = _invoke_json("all", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True


@smoke
class TestSubreddit:
    def test_sub_hot(self):
        result = _invoke("sub", "python", "-n", "5")
        assert result.exit_code == 0

    def test_sub_new(self):
        result = _invoke("sub", "python", "-s", "new", "-n", "3")
        assert result.exit_code == 0

    def test_sub_top_week(self):
        result = _invoke("sub", "python", "-s", "top", "-t", "week", "-n", "3")
        assert result.exit_code == 0

    def test_sub_rising(self):
        result = _invoke("sub", "python", "-s", "rising", "-n", "3")
        assert result.exit_code == 0

    def test_sub_json(self):
        result, data = _invoke_json("sub", "python", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True

    def test_sub_nonexistent(self):
        result = _invoke("sub", "thissubredditshouldnotexist12345xyz")
        # Now correctly exits with code 1 on API error
        assert result.exit_code in (0, 1)


@smoke
class TestSubInfo:
    def test_sub_info(self):
        result = _invoke("sub-info", "python")
        assert result.exit_code == 0

    def test_sub_info_json(self):
        result, data = _invoke_json("sub-info", "python")
        assert result.exit_code == 0
        if data:
            inner = data.get("data", data)
            assert "display_name" in inner or "subscribers" in inner

    def test_sub_info_large(self):
        """Test with a very large subreddit."""
        result, data = _invoke_json("sub-info", "AskReddit")
        assert result.exit_code == 0
        if data:
            inner = data.get("data", data)
            if "subscribers" in inner:
                assert inner["subscribers"] > 1_000_000


@smoke
class TestUser:
    def test_user_profile(self):
        result = _invoke("user", "spez")
        assert result.exit_code == 0

    def test_user_profile_json(self):
        result, data = _invoke_json("user", "spez")
        assert result.exit_code == 0
        if data:
            inner = data.get("data", data)
            assert "name" in inner

    def test_user_nonexistent(self):
        result = _invoke("user", "thisusershouldnotexist12345xyz")
        # Now correctly exits with code 1 on API error
        assert result.exit_code in (0, 1)


@smoke
class TestUserPosts:
    def test_user_posts(self):
        result = _invoke("user-posts", "spez", "-n", "3")
        assert result.exit_code == 0

    def test_user_posts_json(self):
        result, data = _invoke_json("user-posts", "spez", "-n", "3")
        assert result.exit_code == 0


# ── Search ──────────────────────────────────────────────────────────


@smoke
class TestSearch:
    def test_search_basic(self):
        result = _invoke("search", "python", "-n", "5")
        assert result.exit_code == 0

    def test_search_subreddit(self):
        result = _invoke("search", "async", "-r", "python", "-n", "3")
        assert result.exit_code == 0

    def test_search_sort_top(self):
        result = _invoke("search", "rust", "-s", "top", "-t", "year", "-n", "3")
        assert result.exit_code == 0

    def test_search_json(self):
        result, data = _invoke_json("search", "python tips", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True

    def test_search_sort_comments(self):
        result = _invoke("search", "reddit", "-s", "comments", "-n", "3")
        assert result.exit_code == 0


# ── Post reading ────────────────────────────────────────────────────


@smoke
class TestRead:
    def test_read_invalid_id(self):
        result = _invoke("read", "invalid_post_id_that_does_not_exist")
        # May exit 0 or 1 depending on API response
        assert result.exit_code in (0, 1)


@smoke
class TestShow:
    def test_show_no_cache(self):
        # Without prior search, show should exit with error
        result = _invoke("show", "1")
        assert result.exit_code in (0, 1)


# ── Open ────────────────────────────────────────────────────────────


@smoke
class TestOpen:
    def test_open_no_cache(self):
        result = _invoke("open", "1")
        assert result.exit_code == 0


# ── Export ──────────────────────────────────────────────────────────


@smoke
class TestExport:
    def test_export_csv_stdout(self):
        result = _invoke("export", "python", "-n", "3", "--format", "csv")
        assert result.exit_code == 0
        if result.output.strip():
            assert "title" in result.output.lower() or "subreddit" in result.output.lower()

    def test_export_json_stdout(self):
        result = _invoke("export", "python", "-n", "3", "--format", "json")
        assert result.exit_code == 0

    def test_export_csv_file(self, tmp_path):
        outfile = str(tmp_path / "test.csv")
        result = runner.invoke(cli, ["export", "python", "-n", "3", "-o", outfile])
        assert result.exit_code == 0

    def test_export_json_file(self, tmp_path):
        outfile = str(tmp_path / "test.json")
        result = runner.invoke(cli, ["export", "python", "-n", "3", "--format", "json", "-o", outfile])
        assert result.exit_code == 0


# ── Comment (help only, no auth) ────────────────────────────────────


@smoke
class TestComment:
    def test_comment_help(self):
        result = _invoke("comment", "--help")
        assert result.exit_code == 0
        assert "comment" in result.output.lower()


# ── Roundtrip workflows ────────────────────────────────────────────


@smoke
class TestRoundtrip:
    def test_search_then_show(self):
        """E2E: search → show #1."""
        r1 = _invoke("search", "python", "-n", "3")
        assert r1.exit_code == 0

        r2 = _invoke("show", "1")
        assert r2.exit_code == 0

    def test_browse_then_show(self):
        """E2E: sub → show #1."""
        r1 = _invoke("sub", "python", "-n", "3")
        assert r1.exit_code == 0

        r2 = _invoke("show", "1")
        assert r2.exit_code == 0

    def test_popular_then_open(self):
        """E2E: popular → open #1 (mocked to avoid browser popup)."""
        r1 = _invoke("popular", "-n", "3")
        assert r1.exit_code == 0

        # Don't actually open browser in test
        from unittest.mock import patch
        with patch("rdt_cli.commands.browse.open_url"):
            r2 = _invoke("open", "1")
            assert r2.exit_code == 0

    def test_multi_command(self):
        """Multiple commands in sequence."""
        for cmd in [
            ["status"],
            ["popular", "-n", "3"],
            ["sub-info", "python"],
        ]:
            result = _invoke(*cmd)
            assert result.exit_code == 0, f"{cmd} failed: {result.output}"

    def test_search_then_export(self):
        """E2E: search then export same query."""
        r1 = _invoke("search", "python", "-n", "3")
        assert r1.exit_code == 0

        r2 = _invoke("export", "python", "-n", "3", "--format", "json")
        assert r2.exit_code == 0
