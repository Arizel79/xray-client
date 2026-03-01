"""Main CLI interface for xray-client."""

import click
import sys

from src.cli.commands import connection
from src.cli.commands import server, settings, subscribe


@click.group()
@click.version_option(version="0.2.0")
def cli():
    pass


cli.add_command(connection)
cli.add_command(server)
cli.add_command(subscribe)
cli.add_command(settings)



