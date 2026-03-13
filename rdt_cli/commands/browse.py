"""Browse commands: feed, subreddit, popular, user."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import click
from rich.table import Table
from rich.text import Text

from ..client import RedditClient
from ..constants import SORT_OPTIONS, TIME_FILTERS
from ..exceptions import RedditApiError
from ..index_cache import save_index
from ._common import (
    console,
    handle_command,
    output_or_render,
    require_auth,
    structured_output_options,
)

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────


def _format_score(score: int) -> str:
    """Format score with color."""
    if score >= 1000:
        return f"{score / 1000:.1f}k"
    return str(score)


def _format_time(ts: float) -> str:
    """Format Unix timestamp to relative time."""
    now = datetime.now(timezone.utc).timestamp()
    diff = now - ts
    if diff < 3600:
        return f"{int(diff / 60)}m ago"
    if diff < 86400:
        return f"{int(diff / 3600)}h ago"
    if diff < 604800:
        return f"{int(diff / 86400)}d ago"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _render_post_table(posts: list[dict], title: str, show_subreddit: bool = True) -> None:
    """Render a list of posts as a Rich table."""
    if not posts:
        console.print("[yellow]No posts found[/yellow]")
        return

    save_index(posts, source=title[:40])

    table = Table(title=title, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", style="yellow", width=6, justify="right")
    if show_subreddit:
        table.add_column("Subreddit", style="magenta", max_width=15)
    table.add_column("Title", style="bold cyan", max_width=50)
    table.add_column("Author", style="green", max_width=14)
    table.add_column("💬", style="dim", width=5, justify="right")
    table.add_column("Time", style="dim", max_width=10)

    for i, post in enumerate(posts, 1):
        title_text = post.get("title", "-")
        if post.get("stickied"):
            title_text = f"📌 {title_text}"
        if post.get("over_18"):
            title_text = f"🔞 {title_text}"
        if post.get("is_video"):
            title_text = f"🎬 {title_text}"

        row = [
            str(i),
            _format_score(post.get("score", 0)),
        ]
        if show_subreddit:
            row.append(f"r/{post.get('subreddit', '?')}")
        row.extend([
            title_text[:50],
            post.get("author", "-")[:14],
            str(post.get("num_comments", 0)),
            _format_time(post.get("created_utc", 0)),
        ])
        table.add_row(*row)

    console.print(table)
    console.print(f"\n  [dim]💡 Use [bold]rdt show <#>[/bold] to read a post[/dim]")


# ── feed ────────────────────────────────────────────────────────────


@click.command()
@click.option("-n", "--limit", default=25, type=int, help="Number of posts (default: 25)")
@click.option("--after", default=None, help="Pagination cursor")
@structured_output_options
def feed(limit: int, after: str | None, as_json: bool, as_yaml: bool) -> None:
    """Browse your home feed (requires login)"""
    cred = require_auth()

    def _render(data: dict) -> None:
        posts = RedditClient._extract_posts(data)
        _render_post_table(posts, "🏠 Home Feed")
        cursor = RedditClient._extract_after(data)
        if cursor:
            console.print(f"  [dim]▸ More: rdt feed --after {cursor}[/dim]")

    handle_command(cred, action=lambda c: c.get_home(limit=limit, after=after), render=_render, as_json=as_json, as_yaml=as_yaml)


# ── popular ─────────────────────────────────────────────────────────


@click.command()
@click.option("-n", "--limit", default=25, type=int, help="Number of posts")
@click.option("--after", default=None, help="Pagination cursor")
@structured_output_options
def popular(limit: int, after: str | None, as_json: bool, as_yaml: bool) -> None:
    """Browse /r/popular"""
    from ..auth import get_credential

    cred = get_credential()

    def _render(data: dict) -> None:
        posts = RedditClient._extract_posts(data)
        _render_post_table(posts, "🔥 Popular")
        cursor = RedditClient._extract_after(data)
        if cursor:
            console.print(f"  [dim]▸ More: rdt popular --after {cursor}[/dim]")

    handle_command(cred, action=lambda c: c.get_popular(limit=limit, after=after), render=_render, as_json=as_json, as_yaml=as_yaml)


# ── sub (subreddit) ─────────────────────────────────────────────────


@click.command()
@click.argument("subreddit")
@click.option("-s", "--sort", type=click.Choice(SORT_OPTIONS), default="hot", help="Sort order")
@click.option("-t", "--time", "time_filter", type=click.Choice(TIME_FILTERS), default=None, help="Time filter (for top/controversial)")
@click.option("-n", "--limit", default=25, type=int, help="Number of posts")
@click.option("--after", default=None, help="Pagination cursor")
@structured_output_options
def sub(subreddit: str, sort: str, time_filter: str | None, limit: int, after: str | None, as_json: bool, as_yaml: bool) -> None:
    """Browse a subreddit (e.g., rdt sub python)"""
    from ..auth import get_credential

    cred = get_credential()

    def _render(data: dict) -> None:
        posts = RedditClient._extract_posts(data)
        emoji = {"hot": "🔥", "new": "🆕", "top": "🏆", "rising": "📈"}.get(sort, "📋")
        _render_post_table(posts, f"{emoji} r/{subreddit} ({sort})", show_subreddit=False)
        cursor = RedditClient._extract_after(data)
        if cursor:
            console.print(f"  [dim]▸ More: rdt sub {subreddit} -s {sort} --after {cursor}[/dim]")

    handle_command(
        cred,
        action=lambda c: c.get_subreddit(subreddit, sort=sort, limit=limit, after=after, time_filter=time_filter),
        render=_render,
        as_json=as_json,
        as_yaml=as_yaml,
    )


# ── sub-info ────────────────────────────────────────────────────────


@click.command("sub-info")
@click.argument("subreddit")
@structured_output_options
def sub_info(subreddit: str, as_json: bool, as_yaml: bool) -> None:
    """View subreddit info (subscribers, description)"""
    from ..auth import get_credential

    cred = get_credential()

    def _render(data: dict) -> None:
        from rich.panel import Panel

        name = data.get("display_name_prefixed", f"r/{subreddit}")
        desc = data.get("public_description", data.get("description", ""))
        subs = data.get("subscribers", 0)
        active = data.get("accounts_active", 0)
        created = data.get("created_utc", 0)
        nsfw = "🔞 NSFW" if data.get("over18") else ""

        text = (
            f"[bold cyan]{name}[/bold cyan] {nsfw}\n"
            f"👥 {subs:,} subscribers · 🟢 {active:,} online\n"
            f"📅 Created: {_format_time(created)}\n"
        )
        if desc:
            text += f"\n{desc[:300]}"

        panel = Panel(text, title=f"📋 {name}", border_style="cyan")
        console.print(panel)

    handle_command(cred, action=lambda c: c.get_subreddit_about(subreddit), render=_render, as_json=as_json, as_yaml=as_yaml)


# ── user ────────────────────────────────────────────────────────────


@click.command()
@click.argument("username")
@structured_output_options
def user(username: str, as_json: bool, as_yaml: bool) -> None:
    """View a user's profile"""
    from ..auth import get_credential

    cred = get_credential()

    def _render(data: dict) -> None:
        from rich.panel import Panel

        name = data.get("name", username)
        karma_post = data.get("link_karma", 0)
        karma_comment = data.get("comment_karma", 0)
        created = data.get("created_utc", 0)
        is_gold = "⭐ " if data.get("is_gold") else ""

        text = (
            f"[bold cyan]u/{name}[/bold cyan] {is_gold}\n"
            f"📊 Post karma: {karma_post:,} · Comment karma: {karma_comment:,}\n"
            f"📅 Account age: {_format_time(created)}\n"
        )

        panel = Panel(text, title=f"👤 u/{name}", border_style="green")
        console.print(panel)

    handle_command(cred, action=lambda c: c.get_user_about(username), render=_render, as_json=as_json, as_yaml=as_yaml)


# ── user-posts ──────────────────────────────────────────────────────


@click.command("user-posts")
@click.argument("username")
@click.option("-n", "--limit", default=25, type=int, help="Number of posts")
@click.option("--after", default=None, help="Pagination cursor")
@structured_output_options
def user_posts(username: str, limit: int, after: str | None, as_json: bool, as_yaml: bool) -> None:
    """View a user's submitted posts"""
    from ..auth import get_credential

    cred = get_credential()

    def _render(data: dict) -> None:
        posts = RedditClient._extract_posts(data)
        _render_post_table(posts, f"📝 u/{username}'s posts")

    handle_command(cred, action=lambda c: c.get_user_posts(username, limit=limit, after=after), render=_render, as_json=as_json, as_yaml=as_yaml)
