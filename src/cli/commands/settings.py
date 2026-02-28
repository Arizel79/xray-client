"""Settings commands for xray-client CLI."""

import click
import sys

from src.core.config import ConfigManager


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
        config_mgr = ConfigManager()
        config = config_mgr.load()
        
        config.settings.subscription_headers_enable = True
        config_mgr.save(config)
        
        click.echo("Subscription headers enabled")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@headers.command(name="disable")
def headers_disable():
    """Disable subscription headers."""
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
        
        config.settings.subscription_headers_enable = False
        config_mgr.save(config)
        
        click.echo("Subscription headers disabled")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@headers.command(name="status")
def headers_status():
    """Show subscription headers status."""
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
        
        if config.settings.subscription_headers_enable:
            click.echo("Subscription headers: enabled")
        else:
            click.echo("Subscription headers: disabled")
            
        if config.settings.subscription_headers:
            click.echo("\nCurrent headers:")
            for key, value in config.settings.subscription_headers.items():
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
        config_mgr = ConfigManager()
        config = config_mgr.load()
        
        config.settings.subscription_headers[key] = value
        config_mgr.save(config)
        
        click.echo(f"Header set: {key}: {value}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@headers.command(name="unset")
@click.argument("key")
def headers_unset(key: str):
    """Remove a header."""
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
        
        if key in config.settings.subscription_headers:
            del config.settings.subscription_headers[key]
            config_mgr.save(config)
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
        config_mgr = ConfigManager()
        config = config_mgr.load()
        
        config.settings.subscription_headers.clear()
        config_mgr.save(config)
        
        click.echo("All headers cleared")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)