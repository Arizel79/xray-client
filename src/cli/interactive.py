"""Interactive shell for xray-client."""
import click
from click_shell import shell

from src.cli.main import cli as main_cli

@shell(prompt='xray> ', intro='XRAY Client Interactive Shell. Type "exit" to quit.')
def interactive_shell():
    pass

for command_name, command in main_cli.commands.items():
    interactive_shell.add_command(command)

@interactive_shell.command()
def exit():
    raise SystemExit

if __name__ == '__main__':
    interactive_shell()