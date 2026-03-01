"""Main CLI interface for xray-client."""

import click

from src.cli.commands import connection  # Новая группа команд
from src.cli.commands import server, settings, subscribe


@click.group()
@click.version_option(version="0.2.0")
def cli():
    """XRAY Client - Python CLI for VLESS VPN with subscription support."""
    pass


# Add commands from modules
cli.add_command(connection)  # Новая группа
cli.add_command(server)
cli.add_command(subscribe)
cli.add_command(settings)


if __name__ == "__main__":
    cli()
