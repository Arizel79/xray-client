"""Subscription management commands for xray-client CLI."""

import sys

import click

from src.core.config import ConfigManager, Subscription
from src.core.subscription import SubscriptionManager
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
        config_mgr = ConfigManager()

        subscription = Subscription(name=name, url=url)
        config_mgr.add_subscription(subscription)

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
        config_mgr = ConfigManager()
        sub_mgr = SubscriptionManager()

        # Load config to get subscriptions headers
        config = config_mgr.load()
        headers_enable = config.settings.subscription_headers_enable
        headers = config.settings.subscription_headers

        # Get subscriptions to update
        if name:
            subscription = config_mgr.get_subscription(name)
            if not subscription:
                click.echo(f"Error: Subscription '{name}' not found")
                sys.exit(1)
            subscriptions = [subscription]
        else:
            subscriptions = config_mgr.list_subscriptions()

        if not subscriptions:
            click.echo("No subscriptions configured")
            sys.exit(0)

        # Update each subscription
        for sub in subscriptions:
            click.echo(f"Updating subscription: {sub.name}...")

            if headers_enable:
                click.echo(f"  Using headers: {headers}")

            try:
                servers = sub_mgr.update_subscription(
                    sub.url, headers=headers if headers_enable else None
                )
                click.echo(f"  Found {len(servers)} servers")

                # Update config
                config_mgr.update_subscription_servers(sub.name, servers)
                click.echo(f"  Updated successfully")

            except Exception as e:
                click.echo(f"  Error: {e}", err=True)
                continue

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@subscribe.command(name="list")
def subscribe_list():
    """List all subscriptions."""
    try:
        config_mgr = ConfigManager()
        subscriptions = config_mgr.list_subscriptions()

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
        config_mgr = ConfigManager()

        if not config_mgr.get_subscription(name):
            click.echo(f"Error: Subscription '{name}' not found")
            sys.exit(1)

        config_mgr.remove_subscription(name, remove_servers=not keep_servers)

        click.echo(f"Removed subscription: {name}")
        if not keep_servers:
            click.echo("All servers from this subscription were also removed")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
