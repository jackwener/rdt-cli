"""Typed data models for Reddit listings, posts, comments, and profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Post:
    id: str
    name: str
    title: str
    subreddit: str
    author: str
    score: int = 0
    num_comments: int = 0
    created_utc: float = 0.0
    permalink: str = ""
    url: str = ""
    selftext: str = ""
    is_self: bool = True
    over_18: bool = False
    is_video: bool = False
    stickied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Comment:
    id: str
    fullname: str
    author: str
    body: str
    parent_fullname: str = ""
    score: int = 0
    created_utc: float = 0.0
    replies: list[Comment] = field(default_factory=list)
    more_count: int = 0
    more_children: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fullname": self.fullname,
            "author": self.author,
            "body": self.body,
            "parent_fullname": self.parent_fullname,
            "score": self.score,
            "created_utc": self.created_utc,
            "more_count": self.more_count,
            "more_children": list(self.more_children),
            "replies": [reply.to_dict() for reply in self.replies],
        }


@dataclass
class ListingPage:
    items: list[Post]
    after: str | None = None
    before: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "after": self.after,
            "before": self.before,
        }


@dataclass
class PostDetail:
    post: Post
    comments: list[Comment] = field(default_factory=list)
    more_count: int = 0
    more_children: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "post": self.post.to_dict(),
            "comments": [comment.to_dict() for comment in self.comments],
            "more_count": self.more_count,
            "more_children": list(self.more_children),
        }


@dataclass
class UserProfile:
    name: str
    link_karma: int = 0
    comment_karma: int = 0
    created_utc: float = 0.0
    is_gold: bool = False
    is_mod: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubredditInfo:
    display_name: str
    display_name_prefixed: str
    public_description: str = ""
    description: str = ""
    subscribers: int = 0
    accounts_active: int = 0
    created_utc: float = 0.0
    over18: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
