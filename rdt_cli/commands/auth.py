"""Auth commands: login, logout, status, whoami."""

from __future__ import annotations

import click

from ._common import (
    console,
    handle_command,
    maybe_print_structured,
    require_auth,
    structured_output_options,
)


@click.command()
def login() -> None:
    """Extract browser cookies for Reddit authentication"""
    from ..auth import extract_browser_credential, get_credential

    # Check if already logged in
    cred = get_credential()
    if cred:
        console.print("[green]✅ Already authenticated[/green]")
        return

    console.print("[dim]🔍 Searching for Reddit cookies in browsers...[/dim]")
    cred = extract_browser_credential()
    if cred:
        console.print(f"[green]✅ Login successful![/green] ({len(cred.cookies)} cookies extracted)")
    else:
        console.print("[red]❌ No Reddit cookies found.[/red]")
        console.print("  [dim]Please login to reddit.com in your browser first, then retry.[/dim]")


@click.command()
def logout() -> None:
    """Clear saved Reddit cookies"""
    from ..auth import clear_credential

    clear_credential()
    console.print("[green]✅ Credentials cleared[/green]")


@click.command()
@structured_output_options
def status(as_json: bool, as_yaml: bool) -> None:
    """Check authentication status"""
    from ..auth import CREDENTIAL_FILE, get_credential

    cred = get_credential()
    info = {
        "authenticated": cred is not None,
        "cookie_count": len(cred.cookies) if cred else 0,
        "credential_file": str(CREDENTIAL_FILE),
    }

    if maybe_print_structured(info, as_json=as_json, as_yaml=as_yaml):
        return

    if cred:
        console.print(f"[green]✅ Authenticated[/green] ({len(cred.cookies)} cookies)")
        if "reddit_session" in cred.cookies:
            console.print("  [dim]reddit_session: ✓[/dim]")
    else:
        console.print("[yellow]⚠️  Not authenticated[/yellow]")
        console.print("  [dim]Use 'rdt login' to extract cookies from your browser[/dim]")


@click.command()
@structured_output_options
def whoami(as_json: bool, as_yaml: bool) -> None:
    """Show current user profile (karma, account age)"""
    from rich.panel import Panel

    from ._common import format_time

    cred = require_auth()

    def _render(data: dict) -> None:
        name = data.get("name", "?")
        karma_post = data.get("link_karma", 0)
        karma_comment = data.get("comment_karma", 0)
        total_karma = data.get("total_karma", karma_post + karma_comment)
        created = data.get("created_utc", 0)
        is_gold = "⭐ " if data.get("is_gold") else ""
        is_mod = "🛡️ " if data.get("is_mod") else ""

        text = (
            f"[bold cyan]u/{name}[/bold cyan] {is_gold}{is_mod}\n"
            f"📊 Total karma: {total_karma:,}\n"
            f"   Post: {karma_post:,} · Comment: {karma_comment:,}\n"
            f"📅 Joined: {format_time(created)}\n"
        )

        panel = Panel(text, title="👤 Me", border_style="green")
        console.print(panel)

    handle_command(
        cred,
        action=lambda c: c.get_user_about(cred.cookies.get("reddit_user", "me")),
        render=_render,
        as_json=as_json,
        as_yaml=as_yaml,
    )
