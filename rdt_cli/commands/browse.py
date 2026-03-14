"""Browse commands: feed, subreddit, popular, all, user, open."""

from __future__ import annotations

import logging

import click
from rich.panel import Panel
from rich.table import Table

from ..client import RedditClient
from ..constants import SORT_OPTIONS, TIME_FILTERS
from ..index_cache import save_index
from ._common import (
    console,
    format_score,
    format_time,
    handle_command,
    open_url,
    optional_auth,
    require_auth,
    structured_output_options,
)

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────


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
            format_score(post.get("score", 0)),
        ]
        if show_subreddit:
            row.append(f"r/{post.get('subreddit', '?')}")
        row.extend([
            title_text[:50],
            post.get("author", "-")[:14],
            str(post.get("num_comments", 0)),
            format_time(post.get("created_utc", 0)),
        ])
        table.add_row(*row)

    console.print(table)
    console.print("\n  [dim]💡 Use [bold]rdt show <#>[/bold] to read a post[/dim]")


def _listing_render(data: dict, title: str, show_subreddit: bool = True, next_cmd: str = "") -> None:
    """Common render for listing endpoints."""
    posts = RedditClient._extract_posts(data)
    _render_post_table(posts, title, show_subreddit=show_subreddit)
    cursor = RedditClient._extract_after(data)
    if cursor and next_cmd:
        console.print(f"  [dim]▸ More: {next_cmd} --after {cursor}[/dim]")


# ── feed ────────────────────────────────────────────────────────────


@click.command()
@click.option("-n", "--limit", default=25, type=int, help="Number of posts (default: 25)")
@click.option("--after", default=None, help="Pagination cursor")
@structured_output_options
def feed(limit: int, after: str | None, as_json: bool, as_yaml: bool) -> None:
    """Browse your home feed (requires login)"""
    cred = require_auth()
    handle_command(
        cred,
        action=lambda c: c.get_home(limit=limit, after=after),
        render=lambda d: _listing_render(d, "🏠 Home Feed", next_cmd="rdt feed"),
        as_json=as_json,
        as_yaml=as_yaml,
    )


# ── popular ─────────────────────────────────────────────────────────


@click.command()
@click.option("-n", "--limit", default=25, type=int, help="Number of posts")
@click.option("--after", default=None, help="Pagination cursor")
@structured_output_options
def popular(limit: int, after: str | None, as_json: bool, as_yaml: bool) -> None:
    """Browse /r/popular"""
    cred = optional_auth()
    handle_command(
        cred,
        action=lambda c: c.get_popular(limit=limit, after=after),
        render=lambda d: _listing_render(d, "🔥 Popular", next_cmd="rdt popular"),
        as_json=as_json,
        as_yaml=as_yaml,
    )


# ── all ─────────────────────────────────────────────────────────────


@click.command(name="all")
@click.option("-n", "--limit", default=25, type=int, help="Number of posts")
@click.option("--after", default=None, help="Pagination cursor")
@structured_output_options
def all_cmd(limit: int, after: str | None, as_json: bool, as_yaml: bool) -> None:
    """Browse /r/all"""
    cred = optional_auth()
    handle_command(
        cred,
        action=lambda c: c.get_all(limit=limit, after=after),
        render=lambda d: _listing_render(d, "🌍 r/all", next_cmd="rdt all"),
        as_json=as_json,
        as_yaml=as_yaml,
    )


# ── sub (subreddit) ─────────────────────────────────────────────────


@click.command()
@click.argument("subreddit")
@click.option("-s", "--sort", type=click.Choice(SORT_OPTIONS), default="hot", help="Sort order")
@click.option(
    "-t", "--time", "time_filter",
    type=click.Choice(TIME_FILTERS), default=None,
    help="Time filter (for top/controversial)",
)
@click.option("-n", "--limit", default=25, type=int, help="Number of posts")
@click.option("--after", default=None, help="Pagination cursor")
@structured_output_options
def sub(
    subreddit: str, sort: str, time_filter: str | None, limit: int,
    after: str | None, as_json: bool, as_yaml: bool,
) -> None:
    """Browse a subreddit (e.g., rdt sub python)"""
    cred = optional_auth()
    emoji = {"hot": "🔥", "new": "🆕", "top": "🏆", "rising": "📈"}.get(sort, "📋")
    handle_command(
        cred,
        action=lambda c: c.get_subreddit(subreddit, sort=sort, limit=limit, after=after, time_filter=time_filter),
        render=lambda d: _listing_render(
            d,
            f"{emoji} r/{subreddit} ({sort})",
            show_subreddit=False,
            next_cmd=f"rdt sub {subreddit} -s {sort}",
        ),
        as_json=as_json,
        as_yaml=as_yaml,
    )


# ── sub-info ────────────────────────────────────────────────────────


@click.command("sub-info")
@click.argument("subreddit")
@structured_output_options
def sub_info(subreddit: str, as_json: bool, as_yaml: bool) -> None:
    """View subreddit info (subscribers, description)"""
    cred = optional_auth()

    def _render(data: dict) -> None:
        name = data.get("display_name_prefixed", f"r/{subreddit}")
        desc = data.get("public_description", data.get("description", ""))
        subs = data.get("subscribers", 0)
        active = data.get("accounts_active", 0)
        created = data.get("created_utc", 0)
        nsfw = "🔞 NSFW" if data.get("over18") else ""

        text = (
            f"[bold cyan]{name}[/bold cyan] {nsfw}\n"
            f"👥 {subs:,} subscribers · 🟢 {active:,} online\n"
            f"📅 Created: {format_time(created)}\n"
        )
        if desc:
            text += f"\n{desc[:300]}"

        panel = Panel(text, title=f"📋 {name}", border_style="cyan")
        console.print(panel)

    handle_command(
        cred,
        action=lambda c: c.get_subreddit_about(subreddit),
        render=_render, as_json=as_json, as_yaml=as_yaml,
    )


# ── user ────────────────────────────────────────────────────────────


@click.command()
@click.argument("username")
@structured_output_options
def user(username: str, as_json: bool, as_yaml: bool) -> None:
    """View a user's profile"""
    cred = optional_auth()

    def _render(data: dict) -> None:
        name = data.get("name", username)
        karma_post = data.get("link_karma", 0)
        karma_comment = data.get("comment_karma", 0)
        created = data.get("created_utc", 0)
        is_gold = "⭐ " if data.get("is_gold") else ""

        text = (
            f"[bold cyan]u/{name}[/bold cyan] {is_gold}\n"
            f"📊 Post karma: {karma_post:,} · Comment karma: {karma_comment:,}\n"
            f"📅 Account age: {format_time(created)}\n"
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
    cred = optional_auth()
    handle_command(
        cred,
        action=lambda c: c.get_user_posts(username, limit=limit, after=after),
        render=lambda d: _listing_render(d, f"📝 u/{username}'s posts"),
        as_json=as_json,
        as_yaml=as_yaml,
    )


# ── open ────────────────────────────────────────────────────────────


@click.command(name="open")
@click.argument("id_or_index")
def open_post(id_or_index: str) -> None:
    """Open a post in the browser (by ID or index number)

    Examples:
      rdt open 3           # open result #3 in browser
      rdt open 1abc123     # open by post ID
    """
    from ..index_cache import get_item_by_index

    # Try as short-index
    try:
        idx = int(id_or_index)
        item = get_item_by_index(idx)
        if item:
            permalink = item.get("permalink", "")
            if permalink:
                url = f"https://reddit.com{permalink}"
                console.print(f"[dim]Opening: {url}[/dim]")
                open_url(url)
                return
        console.print(f"[yellow]Index {idx} not found in cache[/yellow]")
        return
    except ValueError:
        pass

    # Bare ID or URL
    if id_or_index.startswith("http"):
        open_url(id_or_index)
    else:
        url = f"https://reddit.com/comments/{id_or_index}"
        console.print(f"[dim]Opening: {url}[/dim]")
        open_url(url)
