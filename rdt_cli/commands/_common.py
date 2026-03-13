"""Common helpers for Reddit CLI commands."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any, TypeVar

import click
from rich.console import Console

from ..auth import Credential, get_credential
from ..client import RedditClient
from ..exceptions import RedditApiError, SessionExpiredError, error_code_for_exception

T = TypeVar("T")

console = Console()
error_console = Console(stderr=True)


def require_auth() -> Credential:
    """Get credential or exit with error."""
    cred = get_credential()
    if not cred:
        console.print("[yellow]⚠️  Not logged in[/yellow]. Use [bold]rdt login[/bold] to authenticate")
        sys.exit(1)
    return cred


def get_client(credential: Credential | None = None) -> RedditClient:
    """Create a RedditClient with optional credential."""
    return RedditClient(credential)


def run_client_action(credential: Credential, action: Callable[[RedditClient], T]) -> T:
    """Run an authenticated client action with auto-retry on session expiry."""
    try:
        with get_client(credential) as client:
            return action(client)
    except SessionExpiredError:
        from ..auth import extract_browser_credential

        fresh = extract_browser_credential()
        if fresh:
            with get_client(fresh) as client:
                return action(client)
        raise


def handle_command(
    credential: Credential,
    *,
    action: Callable[[RedditClient], T],
    render: Callable[[T], None] | None = None,
    as_json: bool = False,
    as_yaml: bool = False,
) -> T | None:
    """Run a client action with structured output support.

    - --json → JSON stdout
    - --yaml or non-TTY → YAML (fallback to JSON)
    - Otherwise → rich render
    """
    try:
        data = run_client_action(credential, action)

        if as_json:
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))
            return data

        if as_yaml or not sys.stdout.isatty():
            try:
                import yaml

                click.echo(yaml.dump(data, allow_unicode=True, default_flow_style=False))
            except ImportError:
                click.echo(json.dumps(data, indent=2, ensure_ascii=False))
            return data

        if render:
            render(data)
        return data

    except RedditApiError as exc:
        _print_error(exc)
        return None


def handle_errors(fn: Callable[[], T]) -> T | None:
    """Run arbitrary command logic and catch RedditApiError."""
    try:
        return fn()
    except RedditApiError as exc:
        _print_error(exc)
        return None


def _print_error(exc: RedditApiError) -> None:
    """Print formatted error message."""
    code = error_code_for_exception(exc)
    console.print(f"[red]❌ [{code}] {exc}[/red]")


def structured_output_options(command: Callable) -> Callable:
    """Add --json/--yaml options to a Click command."""
    command = click.option("--yaml", "as_yaml", is_flag=True, help="Output as YAML")(command)
    command = click.option("--json", "as_json", is_flag=True, help="Output as JSON")(command)
    return command


def output_or_render(data: Any, *, as_json: bool, as_yaml: bool, render: Callable) -> None:
    """DRY output routing: JSON / YAML / Rich."""
    if as_json:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    elif as_yaml or not sys.stdout.isatty():
        try:
            import yaml

            click.echo(yaml.dump(data, allow_unicode=True, default_flow_style=False))
        except ImportError:
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        render(data)
