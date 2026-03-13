"""Auth commands: login, logout, status."""

from __future__ import annotations

import json

import click

from ._common import console, structured_output_options


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

    if as_json:
        click.echo(json.dumps(info, indent=2))
        return

    if cred:
        console.print(f"[green]✅ Authenticated[/green] ({len(cred.cookies)} cookies)")
        # Show if reddit_session exists
        if "reddit_session" in cred.cookies:
            console.print("  [dim]reddit_session: ✓[/dim]")
    else:
        console.print("[yellow]⚠️  Not authenticated[/yellow]")
        console.print("  [dim]Use 'rdt login' to extract cookies from your browser[/dim]")
