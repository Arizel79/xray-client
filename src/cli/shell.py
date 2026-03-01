"""Interactive shell for xray-client."""

import click
from click_shell import shell

from src.cli.main import cli as main_cli


@shell(prompt="xray> ", intro='XRAY сlient interactive shell. Type "quit" to exit.')
def shell():
    pass


for command_name, command in main_cli.commands.items():
    shell.add_command(command)
