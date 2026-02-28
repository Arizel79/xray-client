"""Connection commands for xray-client CLI."""

import click
import sys

from src.core.binary_manager import BinaryManager
from src.core.config import ConfigManager
from src.core.config_generator import ConfigGenerator
from src.core.process_manager import ProcessManager
from src.utils.helpers import format_uptime


@click.command()
@click.argument("server_name_or_id")
def connect(server_name_or_id: str):
    """Connect to a server by name or ID."""
    try:
        config_mgr = ConfigManager()
        binary_mgr = BinaryManager()
        process_mgr = ProcessManager()

        # Check if already running
        if process_mgr.is_running():
            click.echo("Already connected. Disconnect first.")
            sys.exit(1)

        # Find server
        server = None
        
        try:
            server_id = int(server_name_or_id)
            server = config_mgr.get_server(server_id)
        except ValueError:
            pass
            
        if not server:
            server = config_mgr.find_server_by_name(server_name_or_id)

        if not server:
            click.echo(f"Error: Server '{server_name_or_id}' not found")
            sys.exit(1)

        click.echo(f"Connecting to {server.name}...")

        # Ensure xray binary is available
        xray_path = binary_mgr.ensure_binary()

        # Generate xray config
        config = config_mgr.load()
        config_gen = ConfigGenerator(config.settings)
        xray_config = config_gen.generate(server)

        # Start xray
        process_mgr.start(xray_path, xray_config)

        # Update current server
        config_mgr.set_current_server(str(server.id))

        click.echo(f"Connected to {server.name}")
        click.echo(f"SOCKS5: {config.settings.listen_host}:{config.settings.listen_socks_port}")
        click.echo(f"HTTP: {config.settings.listen_host}:{config.settings.listen_http_port}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command()
def disconnect():
    """Disconnect current connection."""
    try:
        process_mgr = ProcessManager()
        config_mgr = ConfigManager()

        if not process_mgr.is_running():
            click.echo("Not connected")
            sys.exit(0)

        click.echo("Disconnecting...")
        process_mgr.stop()

        # Clear current server
        config_mgr.set_current_server(None)

        click.echo("Disconnected")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command()
def status():
    """Show connection status."""
    try:
        process_mgr = ProcessManager()
        config_mgr = ConfigManager()

        status = process_mgr.get_status()

        if not status["running"]:
            click.echo("Status: Disconnected")
            sys.exit(0)

        current_server = config_mgr.get_current_server()

        click.echo("Status: Connected")
        if current_server:
            click.echo(f"Server: {current_server.name}")
            click.echo(f"Protocol: {current_server.protocol}")
            click.echo(f"Address: {current_server.address}:{current_server.port}")

        config = config_mgr.load()
        click.echo(f"SOCKS5: {config.settings.listen_host}:{config.settings.listen_socks_port}")
        click.echo(f"HTTP: {config.settings.listen_host}:{config.settings.listen_http_port}")

        click.echo(f"\nProcess Info:")
        click.echo(f"  PID: {status['pid']}")
        click.echo(f"  Uptime: {format_uptime(status['uptime'])}")
        click.echo(f"  Memory: {status['memory_mb']} MB")
        click.echo(f"  CPU: {status['cpu_percent']}%")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)