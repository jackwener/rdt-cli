"""Search and export commands."""

from __future__ import annotations

import csv
import io
import json
import logging
import sys

import click
from rich.table import Table

from ..client import RedditClient
from ..constants import SEARCH_SORT_OPTIONS, TIME_FILTERS
from ..exceptions import RedditApiError
from ..index_cache import save_index
from ._common import (
    compact_posts,
    console,
    exit_for_error,
    format_score,
    listing_options,
    maybe_print_structured,
    optional_auth,
    save_output_to_file,
)

logger = logging.getLogger(__name__)


def _render_search_table(
    posts: list[dict], query: str, full_text: bool = False,
) -> None:
    """Render search results as a Rich table."""
    if not posts:
        console.print(f"[yellow]No results for '{query}'[/yellow]")
        return

    save_index(posts, source=f"search:{query}")
    max_title = 200 if full_text else 45

    table = Table(title=f'🔍 Search: "{query}" — {len(posts)} results', show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", style="yellow", width=6, justify="right")
    table.add_column("Subreddit", style="magenta", max_width=15)
    table.add_column(
        "Title", style="bold cyan",
        max_width=max_title if not full_text else None,
    )
    table.add_column("Author", style="green", max_width=12)
    table.add_column("💬", style="dim", width=5, justify="right")

    for i, post in enumerate(posts, 1):
        title_text = post.get("title", "-")
        if not full_text:
            title_text = title_text[:max_title]
        table.add_row(
            str(i),
            format_score(post.get("score", 0)),
            f"r/{post.get('subreddit', '?')}",
            title_text,
            post.get("author", "-")[:12],
            str(post.get("num_comments", 0)),
        )

    console.print(table)
    console.print("\n  [dim]💡 Use [bold]rdt show <#>[/bold] to read a result[/dim]")


# ── search ──────────────────────────────────────────────────────────


@click.command()
@click.argument("query")
@click.option("-r", "--subreddit", default=None, help="Search within subreddit")
@click.option(
    "-s", "--sort", type=click.Choice(SEARCH_SORT_OPTIONS),
    default="relevance", help="Sort order",
)
@click.option(
    "-t", "--time", "time_filter",
    type=click.Choice(TIME_FILTERS), default="all", help="Time filter",
)
@click.option("-n", "--limit", default=25, type=int, help="Number of results")
@click.option("--after", default=None, help="Pagination cursor")
@listing_options
def search(
    query: str,
    subreddit: str | None,
    sort: str,
    time_filter: str,
    limit: int,
    after: str | None,
    as_json: bool,
    as_yaml: bool,
    output_file: str | None,
    full_text: bool,
    compact: bool,
) -> None:
    """Search Reddit posts

    Examples:
      rdt search "python async"
      rdt search "rust vs go" -r programming --sort top --time year
    """
    cred = optional_auth()

    try:
        with RedditClient(cred) as client:
            data = client.search(
                query=query,
                subreddit=subreddit,
                sort=sort,
                time_filter=time_filter,
                limit=limit,
                after=after,
            )

        posts = RedditClient._extract_posts(data)
        if posts:
            save_index(posts, source=f"search:{query}")

        # --output: save to file
        if output_file:
            out_data = compact_posts(posts) if compact else data
            save_output_to_file(out_data, output_file)
            return

        # --compact: strip fields for structured output
        out_data = data
        if compact and (as_json or as_yaml):
            out_data = compact_posts(posts)

        if maybe_print_structured(out_data, as_json=as_json, as_yaml=as_yaml):
            # Show pagination hint
            cursor = RedditClient._extract_after(data)
            if cursor:
                console.print(
                    f'  [dim]▸ More: rdt search "{query}" --after {cursor}[/dim]',
                )
            return

        _render_search_table(posts, query, full_text=full_text)

        # Show pagination hint
        cursor = RedditClient._extract_after(data)
        if cursor and sys.stdout.isatty():
            console.print(f'  [dim]▸ More: rdt search "{query}" --after {cursor}[/dim]')

    except RedditApiError as exc:
        exit_for_error(exc, as_json=as_json, as_yaml=as_yaml, prefix="Search failed")


# ── export ──────────────────────────────────────────────────────────


@click.command()
@click.argument("query")
@click.option("-r", "--subreddit", default=None, help="Search within subreddit")
@click.option("-s", "--sort", type=click.Choice(SEARCH_SORT_OPTIONS), default="relevance", help="Sort order")
@click.option("-n", "--count", default=50, type=int, help="Number of results to export")
@click.option("-o", "--output", "output_file", default=None, help="Output file path")
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv", help="Output format")
def export(query: str, subreddit: str | None, sort: str, count: int, output_file: str | None, fmt: str) -> None:
    """Export search results to CSV or JSON

    Examples:
      rdt export "machine learning" -n 100 -o results.csv
      rdt export "python tips" --format json -o tips.json
    """
    cred = optional_auth()
    all_posts: list[dict] = []
    after = None

    try:
        with RedditClient(cred) as client:
            pages = 0
            max_pages = (count + 24) // 25

            while len(all_posts) < count and pages < max_pages:
                data = client.search(query=query, subreddit=subreddit, sort=sort, limit=25, after=after)
                posts = RedditClient._extract_posts(data)
                if not posts:
                    break
                all_posts.extend(posts)
                after = RedditClient._extract_after(data)
                if not after:
                    break
                pages += 1

        all_posts = all_posts[:count]

        if not all_posts:
            console.print(f"[yellow]No results found for '{query}'[/yellow]")
            return

        if fmt == "json":
            text = json.dumps(all_posts, indent=2, ensure_ascii=False)
        else:
            buf = io.StringIO()
            fieldnames = ["title", "subreddit", "author", "score", "num_comments", "url", "permalink"]
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for p in all_posts:
                row = {
                    "title": p.get("title", ""),
                    "subreddit": p.get("subreddit", ""),
                    "author": p.get("author", ""),
                    "score": p.get("score", 0),
                    "num_comments": p.get("num_comments", 0),
                    "url": p.get("url", ""),
                    "permalink": f"https://reddit.com{p.get('permalink', '')}",
                }
                writer.writerow(row)
            text = buf.getvalue()

        if output_file:
            encoding = "utf-8-sig" if fmt == "csv" else "utf-8"
            with open(output_file, "w", encoding=encoding) as f:
                f.write(text)
            console.print(f"[green]✅ Exported {len(all_posts)} results to {output_file}[/green]")
        else:
            click.echo(text)

    except RedditApiError as exc:
        exit_for_error(exc, prefix="Export failed")
