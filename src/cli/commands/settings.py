"""Settings commands for xray-client CLI."""

import sys

import click

from src.services.xray_service import XrayService


@click.group()
def settings():
    """Manage settings."""
    pass


@settings.group()
def headers():
    """Manage subscription headers."""
    pass


@headers.command(name="enable")
def headers_enable():
    """Enable subscription headers."""
    try:
        service = XrayService()
        service.set_subscription_headers_enabled(True)
        click.echo("Subscription headers enabled")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@headers.command(name="disable")
def headers_disable():
    """Disable subscription headers."""
    try:
        service = XrayService()
        service.set_subscription_headers_enabled(False)
        click.echo("Subscription headers disabled")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@headers.command(name="status")
def headers_status():
    """Show subscription headers status."""
    try:
        service = XrayService()
        settings = service.get_settings()

        if settings.subscription_headers_enable:
            click.echo("Subscription headers: enabled")
        else:
            click.echo("Subscription headers: disabled")

        if settings.subscription_headers:
            click.echo("\nCurrent headers:")
            for key, value in settings.subscription_headers.items():
                click.echo(f"  {key}: {value}")
        else:
            click.echo("No headers configured")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@headers.command(name="set")
@click.argument("key")
@click.argument("value")
def headers_set(key: str, value: str):
    """Set a header key-value pair."""
    try:
        service = XrayService()
        service.set_subscription_header(key, value)
        click.echo(f"Header set: {key}: {value}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@headers.command(name="unset")
@click.argument("key")
def headers_unset(key: str):
    """Remove a header."""
    try:
        service = XrayService()
        if service.remove_subscription_header(key):
            click.echo(f"Header removed: {key}")
        else:
            click.echo(f"Header '{key}' not found")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@headers.command(name="clear")
def headers_clear():
    """Clear all headers."""
    try:
        service = XrayService()
        service.clear_subscription_headers()
        click.echo("All headers cleared")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)