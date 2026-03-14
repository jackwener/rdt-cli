"""Parsers for Reddit JSON payloads."""

from __future__ import annotations

from typing import Any

from .models import Comment, ListingPage, Post, PostDetail, SubredditInfo, UserProfile


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_post(payload: dict[str, Any]) -> Post:
    return Post(
        id=str(payload.get("id", "")),
        name=str(payload.get("name", payload.get("fullname", ""))),
        title=str(payload.get("title", "")),
        subreddit=str(payload.get("subreddit", "")),
        author=str(payload.get("author", "")),
        score=_as_int(payload.get("score")),
        num_comments=_as_int(payload.get("num_comments")),
        created_utc=_as_float(payload.get("created_utc")),
        permalink=str(payload.get("permalink", "")),
        url=str(payload.get("url", "")),
        selftext=str(payload.get("selftext", "")),
        is_self=bool(payload.get("is_self", True)),
        over_18=bool(payload.get("over_18", False)),
        is_video=bool(payload.get("is_video", False)),
        stickied=bool(payload.get("stickied", False)),
    )


def parse_listing(data: dict[str, Any]) -> ListingPage:
    listing = data.get("data", {})
    children = listing.get("children", [])
    posts = [parse_post(child.get("data", child)) for child in children]
    return ListingPage(
        items=posts,
        after=listing.get("after"),
        before=listing.get("before"),
    )


def _parse_comment_node(node: dict[str, Any]) -> Comment | None:
    kind = node.get("kind")
    data = node.get("data", {})
    if kind == "more":
        return Comment(
            id=str(data.get("id", "")),
            fullname=str(data.get("name", "")),
            author="[more]",
            body="",
            parent_fullname=str(data.get("parent_id", "")),
            score=0,
            created_utc=0.0,
            replies=[],
            more_count=len(data.get("children", []) or []),
            more_children=[str(child) for child in data.get("children", []) or []],
        )

    if kind != "t1":
        return None

    replies_payload = data.get("replies", {})
    replies: list[Comment] = []
    if isinstance(replies_payload, dict):
        for child in replies_payload.get("data", {}).get("children", []):
            parsed = _parse_comment_node(child)
            if parsed is not None:
                replies.append(parsed)

    return Comment(
        id=str(data.get("id", "")),
        fullname=str(data.get("name", "")),
        author=str(data.get("author", "[deleted]")),
        body=str(data.get("body", "")),
        parent_fullname=str(data.get("parent_id", "")),
        score=_as_int(data.get("score")),
        created_utc=_as_float(data.get("created_utc")),
        replies=replies,
    )


def _collect_more_ids(comment: Comment) -> list[str]:
    collected: list[str] = []
    for reply in comment.replies:
        if reply.more_children:
            collected.extend(reply.more_children)
        collected.extend(_collect_more_ids(reply))
    return collected


def parse_post_detail(data: list[dict[str, Any]] | dict[str, Any] | PostDetail) -> PostDetail:
    if isinstance(data, PostDetail):
        return data
    if not isinstance(data, list) or not data:
        return PostDetail(post=parse_post(data if isinstance(data, dict) else {}), comments=[])

    post_listing = data[0].get("data", {}).get("children", [])
    post_payload = post_listing[0].get("data", {}) if post_listing else {}

    comments_listing = data[1].get("data", {}).get("children", []) if len(data) > 1 else []
    comments: list[Comment] = []
    more_count = 0
    more_children: list[str] = []
    for child in comments_listing:
        parsed = _parse_comment_node(child)
        if parsed is None:
            continue
        if parsed.author == "[more]":
            more_count += parsed.more_count or 1
            more_children.extend(parsed.more_children)
            continue
        more_children.extend(_collect_more_ids(parsed))
        comments.append(parsed)

    return PostDetail(
        post=parse_post(post_payload),
        comments=comments,
        more_count=more_count,
        more_children=more_children,
    )


def parse_user_profile(data: dict[str, Any]) -> UserProfile:
    inner = data.get("data", data)
    return UserProfile(
        name=str(inner.get("name", "")),
        link_karma=_as_int(inner.get("link_karma")),
        comment_karma=_as_int(inner.get("comment_karma")),
        created_utc=_as_float(inner.get("created_utc")),
        is_gold=bool(inner.get("is_gold", False)),
        is_mod=bool(inner.get("is_mod", False)),
    )


def parse_subreddit_info(data: dict[str, Any]) -> SubredditInfo:
    inner = data.get("data", data)
    display_name = str(inner.get("display_name", ""))
    prefixed = str(inner.get("display_name_prefixed", f"r/{display_name}" if display_name else ""))
    return SubredditInfo(
        display_name=display_name,
        display_name_prefixed=prefixed,
        public_description=str(inner.get("public_description", "")),
        description=str(inner.get("description", "")),
        subscribers=_as_int(inner.get("subscribers")),
        accounts_active=_as_int(inner.get("accounts_active")),
        created_utc=_as_float(inner.get("created_utc")),
        over18=bool(inner.get("over18", False)),
    )


def compact_post_models(posts: list[Post]) -> list[dict[str, Any]]:
    return [post.to_dict() for post in posts]


def parse_morechildren_response(data: dict[str, Any]) -> list[Comment]:
    """Parse /api/morechildren response into typed comments."""
    things = data.get("json", {}).get("data", {}).get("things", [])
    comments: list[Comment] = []
    for thing in things:
        parsed = _parse_comment_node(thing)
        if parsed is not None and parsed.author != "[more]":
            comments.append(parsed)
    return comments
