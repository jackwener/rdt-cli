from __future__ import annotations

import json
from pathlib import Path

from rdt_cli.parser import (
    parse_listing,
    parse_morechildren_response,
    parse_post_detail,
    parse_subreddit_info,
    parse_user_profile,
)


def _fixture(name: str):
    path = Path(__file__).parent / "fixtures" / name
    return json.loads(path.read_text())


def test_parse_listing_fixture() -> None:
    listing = parse_listing(_fixture("listing.json"))

    assert listing.after == "t3_after"
    assert len(listing.items) == 2
    assert listing.items[0].title == "Async Python Tips"
    assert listing.items[0].stickied is True
    assert listing.items[1].over_18 is True
    assert listing.items[1].is_video is True


def test_parse_post_detail_fixture() -> None:
    detail = parse_post_detail(_fixture("post_detail.json"))

    assert detail.post.id == "abc123"
    assert len(detail.comments) == 1
    assert detail.comments[0].author == "bob"
    assert detail.comments[0].replies[0].author == "carol"
    assert detail.more_count == 3
    assert detail.more_children == ["c3", "c4", "c5"]


def test_parse_morechildren_fixture() -> None:
    comments = parse_morechildren_response(_fixture("morechildren.json"))

    assert [comment.id for comment in comments] == ["c3", "c4"]
    assert comments[0].parent_fullname == "t3_abc123"
    assert comments[1].parent_fullname == "t1_c1"


def test_parse_user_profile() -> None:
    profile = parse_user_profile(
        {"data": {"name": "spez", "link_karma": 11, "comment_karma": 22, "created_utc": 123.0, "is_gold": True}}
    )

    assert profile.name == "spez"
    assert profile.link_karma == 11
    assert profile.is_gold is True


def test_parse_subreddit_info() -> None:
    info = parse_subreddit_info(
        {
            "data": {
                "display_name": "python",
                "display_name_prefixed": "r/python",
                "public_description": "Python news",
                "subscribers": 100,
                "accounts_active": 5,
                "created_utc": 1.0,
                "over18": False,
            }
        }
    )

    assert info.display_name_prefixed == "r/python"
    assert info.public_description == "Python news"
    assert info.subscribers == 100
