"""Search result index cache for short-index navigation (rdt show 3)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from .constants import CONFIG_DIR

logger = logging.getLogger(__name__)

INDEX_CACHE_FILE = CONFIG_DIR / "index_cache.json"


def save_index(items: list[dict], source: str = "search") -> None:
    """Save a list of posts/items to the index cache."""
    if not items:
        return
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    entries = []
    for item in items:
        entry = {
            "id": item.get("id", ""),
            "name": item.get("name", ""),  # fullname like t3_abc123
            "title": item.get("title", ""),
            "subreddit": item.get("subreddit", ""),
            "author": item.get("author", ""),
            "score": item.get("score", 0),
            "num_comments": item.get("num_comments", 0),
            "permalink": item.get("permalink", ""),
            "url": item.get("url", ""),
        }
        if entry["id"]:
            entries.append(entry)

    payload = {
        "source": source,
        "saved_at": time.time(),
        "count": len(entries),
        "items": entries,
    }
    INDEX_CACHE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    INDEX_CACHE_FILE.chmod(0o600)
    logger.debug("Saved %d items to index cache (source=%s)", len(entries), source)


def get_item_by_index(index: int) -> dict | None:
    """Get a cached item by 1-based index."""
    if index <= 0 or not INDEX_CACHE_FILE.exists():
        return None
    try:
        data = json.loads(INDEX_CACHE_FILE.read_text())
        items = data.get("items", [])
        if index <= len(items):
            return items[index - 1]
        return None
    except (OSError, json.JSONDecodeError, IndexError):
        return None


def get_index_info() -> dict[str, Any]:
    """Get metadata about the current index cache."""
    if not INDEX_CACHE_FILE.exists():
        return {"exists": False, "count": 0}
    try:
        data = json.loads(INDEX_CACHE_FILE.read_text())
        return {
            "exists": True,
            "count": data.get("count", 0),
            "source": data.get("source", ""),
            "saved_at": data.get("saved_at", 0),
        }
    except (OSError, json.JSONDecodeError):
        return {"exists": False, "count": 0}
