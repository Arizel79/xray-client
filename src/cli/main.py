"""Main CLI interface for xray-client."""

import click

from src.cli.commands import (
    connect, disconnect, status,
    server,
    subscribe,
    settings
)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """XRAY Client - Python CLI for VLESS VPN with subscription support."""
    pass


# Add commands from modules
cli.add_command(connect)
cli.add_command(disconnect)
cli.add_command(status)
cli.add_command(server)
cli.add_command(subscribe)
cli.add_command(settings)


if __name__ == "__main__":
    cli()