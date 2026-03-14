"""Post commands: read, show, comments."""

from __future__ import annotations

import logging

import click
from rich.panel import Panel

from ..client import RedditClient
from ..exceptions import RedditApiError
from ..index_cache import get_index_info, get_item_by_index
from ._common import console, format_score, output_or_render, structured_output_options

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────


def _render_post_detail(data: list | dict) -> None:
    """Render a post with its comments."""
    if isinstance(data, list) and len(data) >= 1:
        # [post_listing, comments_listing]
        post_listing = data[0]
        post_children = post_listing.get("data", {}).get("children", [])
        post = post_children[0].get("data", {}) if post_children else {}

        comments_listing = data[1] if len(data) > 1 else {}
        comment_children = comments_listing.get("data", {}).get("children", [])
    else:
        post = data if isinstance(data, dict) else {}
        comment_children = []

    # Render post
    title = post.get("title", "Untitled")
    author = post.get("author", "?")
    subreddit = post.get("subreddit", "?")
    score = post.get("score", 0)
    num_comments = post.get("num_comments", 0)
    selftext = post.get("selftext", "")
    url = post.get("url", "")
    is_self = post.get("is_self", True)
    permalink = post.get("permalink", "")

    post_text = (
        f"[bold cyan]{title}[/bold cyan]\n"
        f"[dim]r/{subreddit}[/dim] · [green]u/{author}[/green] · "
        f"[yellow]⬆ {score}[/yellow] · 💬 {num_comments}\n"
    )

    if not is_self and url:
        post_text += f"\n🔗 {url}\n"

    if selftext:
        # Truncate very long posts
        if len(selftext) > 1500:
            selftext = selftext[:1500] + "\n\n... [truncated]"
        post_text += f"\n{selftext}"

    if permalink:
        post_text += f"\n\n[dim]https://reddit.com{permalink}[/dim]"

    panel = Panel(post_text, title="📰 Post", border_style="cyan")
    console.print(panel)

    # Render comments
    if comment_children:
        console.print()
        _render_comments(comment_children, depth=0, max_depth=3)


def _render_comments(children: list[dict], depth: int = 0, max_depth: int = 3) -> None:
    """Recursively render comment tree."""
    for child in children:
        if child.get("kind") != "t1":
            continue
        comment = child.get("data", {})
        author = comment.get("author", "[deleted]")
        body = comment.get("body", "")
        score = comment.get("score", 0)

        indent = "  " * depth
        score_color = "yellow" if score > 0 else "red" if score < 0 else "dim"

        # Truncate long comments
        if len(body) > 300:
            body = body[:300] + "..."

        console.print(
            f"{indent}[green]u/{author}[/green] [{score_color}]⬆ {score}[/{score_color}]"
        )
        for line in body.split("\n"):
            console.print(f"{indent}  {line}")
        console.print()

        # Render replies
        if depth < max_depth:
            replies = comment.get("replies", "")
            if isinstance(replies, dict):
                reply_children = replies.get("data", {}).get("children", [])
                if reply_children:
                    _render_comments(reply_children, depth=depth + 1, max_depth=max_depth)


# ── read ────────────────────────────────────────────────────────────


@click.command()
@click.argument("post_id")
@click.option("-s", "--sort", default="best", type=click.Choice(["best", "top", "new", "controversial", "old", "qa"]), help="Comment sort")
@click.option("-n", "--limit", default=25, type=int, help="Number of comments")
@structured_output_options
def read(post_id: str, sort: str, limit: int, as_json: bool, as_yaml: bool) -> None:
    """Read a post and its comments by ID

    Example: rdt read 1abc123
    """
    from ..auth import get_credential

    cred = get_credential()

    try:
        with RedditClient(cred) as client:
            data = client.get_post_comments(post_id=post_id, sort=sort, limit=limit)
        output_or_render(data, as_json=as_json, as_yaml=as_yaml, render=_render_post_detail)
    except RedditApiError as exc:
        console.print(f"[red]❌ Failed to load post: {exc}[/red]")


# ── show (short-index) ──────────────────────────────────────────────


@click.command()
@click.argument("index", type=int)
@click.option("-s", "--sort", default="best", type=click.Choice(["best", "top", "new", "controversial", "old", "qa"]), help="Comment sort")
@click.option("-n", "--limit", default=25, type=int, help="Number of comments")
@structured_output_options
def show(index: int, sort: str, limit: int, as_json: bool, as_yaml: bool) -> None:
    """Read a post by its index from last listing (e.g., rdt show 3)

    Use after rdt feed, rdt sub, rdt search, etc.
    """
    item = get_item_by_index(index)
    if not item:
        info = get_index_info()
        if not info.get("exists"):
            console.print("[yellow]No cached results. Run rdt feed, rdt sub, or rdt search first.[/yellow]")
        else:
            console.print(f"[yellow]Index {index} out of range (total: {info.get('count', 0)})[/yellow]")
        return

    post_id = item.get("id", "")
    if not post_id:
        console.print("[red]❌ Cached item has no post ID[/red]")
        return

    # Show brief info from cache
    console.print(
        f"  [dim]#{index}[/dim] [cyan]{item.get('title', '-')[:60]}[/cyan] "
        f"[dim]r/{item.get('subreddit', '?')}[/dim]  "
        f"[yellow]⬆ {item.get('score', 0)}[/yellow]"
    )
    console.print()

    # Fetch full post + comments
    from ..auth import get_credential

    cred = get_credential()

    try:
        with RedditClient(cred) as client:
            data = client.get_post_comments(post_id=post_id, sort=sort, limit=limit)
        output_or_render(data, as_json=as_json, as_yaml=as_yaml, render=_render_post_detail)
    except RedditApiError as exc:
        console.print(f"[red]❌ Failed to load post: {exc}[/red]")
