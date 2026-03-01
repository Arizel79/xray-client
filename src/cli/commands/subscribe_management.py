"""Subscription management commands for xray-client CLI."""

import sys

import click

from src.services.xray_service import XrayService
from src.utils.helpers import format_timestamp, truncate_string


@click.group()
def subscribe():
    """Manage subscriptions."""
    pass


@subscribe.command(name="add")
@click.argument("name")
@click.argument("url")
def subscribe_add(name: str, url: str):
    """Add a subscription."""
    try:
        service = XrayService()
        service.add_subscription(name, url)
        click.echo(f"Added subscription: {name}")
        click.echo(f"URL: {truncate_string(url, 60)}")
        click.echo("\nRun 'subscribe update' to fetch servers")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@subscribe.command(name="update")
@click.argument("name", required=False)
def subscribe_update(name: str | None):
    """Update subscription(s)."""
    try:
        service = XrayService()

        if name:
            sub = service.get_subscription(name)
            if not sub:
                click.echo(f"Error: Subscription '{name}' not found")
                sys.exit(1)
            click.echo(f"Updating subscription: {name}...")
            servers = service.update_subscription(name)
            click.echo(f"  Found {len(servers)} servers")
            click.echo("  Updated successfully")
        else:
            subscriptions = service.list_subscriptions()
            if not subscriptions:
                click.echo("No subscriptions configured")
                sys.exit(0)

            results = service.update_all_subscriptions()
            for sub_name, count, error in results:
                if error:
                    click.echo(f"{sub_name}: Error - {error}", err=True)
                else:
                    click.echo(f"{sub_name}: Updated {count} servers")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@subscribe.command(name="list")
def subscribe_list():
    """List all subscriptions."""
    try:
        service = XrayService()
        subscriptions = service.list_subscriptions()

        if not subscriptions:
            click.echo("No subscriptions configured")
            sys.exit(0)

        click.echo(f"Total subscriptions: {len(subscriptions)}\n")

        for sub in subscriptions:
            click.echo(f"Name: {sub.name}")
            click.echo(f"URL: {truncate_string(sub.url, 70)}")
            click.echo(f"Last Update: {format_timestamp(sub.last_update)}")
            click.echo(f"Enabled: {sub.enabled}")
            click.echo()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@subscribe.command(name="remove")
@click.argument("name")
@click.option(
    "--keep-servers", is_flag=True, help="Keep servers from this subscription"
)
def subscribe_remove(name: str, keep_servers: bool):
    """Remove a subscription."""
    try:
        service = XrayService()
        if not service.get_subscription(name):
            click.echo(f"Error: Subscription '{name}' not found")
            sys.exit(1)

        service.remove_subscription(name, remove_servers=not keep_servers)

        click.echo(f"Removed subscription: {name}")
        if not keep_servers:
            click.echo("All servers from this subscription were also removed")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)