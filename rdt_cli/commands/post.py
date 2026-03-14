"""Post commands: read, show, comments."""

from __future__ import annotations

import logging

import click
from rich.panel import Panel

from ..index_cache import get_index_info, get_item_by_index
from ..models import Comment, PostDetail
from ..parser import parse_morechildren_response, parse_post_detail
from ._common import (
    console,
    handle_command,
    optional_auth,
    structured_output_options,
)

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────


def _attach_more_comments(detail: PostDetail, more_comments: list[Comment]) -> PostDetail:
    """Attach expanded comments back into the existing tree by parent fullname."""
    comment_map: dict[str, Comment] = {}

    def _walk(comment: Comment) -> None:
        comment_map[comment.fullname] = comment
        for reply in comment.replies:
            _walk(reply)

    for comment in detail.comments:
        _walk(comment)

    for comment in more_comments:
        if comment.fullname in comment_map:
            continue
        parent = comment.parent_fullname
        if parent == detail.post.name or not parent:
            detail.comments.append(comment)
            _walk(comment)
            continue

        parent_comment = comment_map.get(parent)
        if parent_comment is not None:
            parent_comment.replies.append(comment)
            _walk(comment)
        else:
            detail.comments.append(comment)
            _walk(comment)

    detail.more_count = max(0, detail.more_count - len(more_comments))
    detail.more_children = []
    return detail


def _render_post_detail(data: PostDetail | list | dict) -> None:
    """Render a post with its comments."""
    detail = parse_post_detail(data)
    post = detail.post

    # Render post
    title = post.title or "Untitled"
    author = post.author or "?"
    subreddit = post.subreddit or "?"
    score = post.score
    num_comments = post.num_comments
    selftext = post.selftext
    url = post.url
    is_self = post.is_self
    permalink = post.permalink

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
    if detail.comments:
        console.print()
        _render_comments(detail.comments, depth=0, max_depth=3)
        if detail.more_count:
            console.print(f"[dim]... {detail.more_count} more comments not expanded[/dim]")


def _render_comments(children, depth: int = 0, max_depth: int = 3) -> None:
    """Recursively render comment tree."""
    for comment in children:
        author = comment.author or "[deleted]"
        body = comment.body
        score = comment.score

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
            if comment.replies:
                _render_comments(comment.replies, depth=depth + 1, max_depth=max_depth)


# ── read ────────────────────────────────────────────────────────────


@click.command()
@click.argument("post_id")
@click.option(
    "-s", "--sort", default="best",
    type=click.Choice(["best", "top", "new", "controversial", "old", "qa"]),
    help="Comment sort",
)
@click.option("-n", "--limit", default=25, type=int, help="Number of comments")
@click.option("--expand-more", is_flag=True, help="Expand top-level 'more comments' entries")
@structured_output_options
def read(post_id: str, sort: str, limit: int, expand_more: bool, as_json: bool, as_yaml: bool) -> None:
    """Read a post and its comments by ID

    Example: rdt read 1abc123
    """
    cred = optional_auth()
    def _action(client):
        raw = client.get_post_comments(post_id=post_id, sort=sort, limit=limit)
        if not expand_more:
            return raw
        detail = parse_post_detail(raw)
        if detail.more_children:
            expanded = client.get_more_comments(post_id, detail.more_children, sort=sort)
            detail = _attach_more_comments(detail, parse_morechildren_response(expanded))
        if as_json or as_yaml:
            return detail.to_dict()
        return detail

    handle_command(cred, action=_action, render=_render_post_detail, as_json=as_json, as_yaml=as_yaml)


# ── show (short-index) ──────────────────────────────────────────────


@click.command()
@click.argument("index", type=int)
@click.option(
    "-s", "--sort", default="best",
    type=click.Choice(["best", "top", "new", "controversial", "old", "qa"]),
    help="Comment sort",
)
@click.option("-n", "--limit", default=25, type=int, help="Number of comments")
@click.option("--expand-more", is_flag=True, help="Expand top-level 'more comments' entries")
@structured_output_options
def show(index: int, sort: str, limit: int, expand_more: bool, as_json: bool, as_yaml: bool) -> None:
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
    cred = optional_auth()
    def _action(client):
        raw = client.get_post_comments(post_id=post_id, sort=sort, limit=limit)
        if not expand_more:
            return raw
        detail = parse_post_detail(raw)
        if detail.more_children:
            expanded = client.get_more_comments(post_id, detail.more_children, sort=sort)
            detail = _attach_more_comments(detail, parse_morechildren_response(expanded))
        if as_json or as_yaml:
            return detail.to_dict()
        return detail

    handle_command(cred, action=_action, render=_render_post_detail, as_json=as_json, as_yaml=as_yaml)
