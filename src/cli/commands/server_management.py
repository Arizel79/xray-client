"""Server management commands for xray-client CLI."""

import sys

import click

from src.core.config import ConfigManager
from src.core.process_manager import ProcessManager
from src.parsers.base import BaseParser
from src.parsers.vless import VLESSParser
from src.parsers.vmess import VMessParser


@click.group()
def server():
    """Manage servers."""
    pass


@server.command(name="list")
@click.option(
    "-n",
    "--no-subscrition-sorting",
    is_flag=True,
    help="Don`t group servers by subscription",
)
def server_list(no_subscrition_sorting):
    """List all servers."""
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
        servers = config.servers

        if not servers:
            click.echo("No servers configured")
            sys.exit(0)

        id_width = 3

        if not no_subscrition_sorting:
            subscriptions = {sub.name: sub.url for sub in config.subscriptions}
            grouped = {}
            standalone = []

            for server in servers:
                if server.subscription:
                    grouped.setdefault(server.subscription, []).append(server)
                else:
                    standalone.append(server)

            for sub_name in grouped:
                grouped[sub_name].sort(key=lambda s: s.name.lower())
            standalone.sort(key=lambda s: s.name.lower())

            for sub_name, sub_servers in grouped.items():
                url = subscriptions.get(sub_name, "URL not found")
                click.echo(f'Subscription "{sub_name}" ({url}):')

                for idx, server in enumerate(sub_servers, start=1):
                    marker = "  "
                    click.echo(f"{marker}{server.in_list_str()}")
                click.echo()

            if standalone:
                click.echo("Servers (without subscription):")
                if standalone:
                    for server in standalone:
                        marker = "  "
                        click.echo(f"{marker}{server.in_list_str()}")
                click.echo()
        else:
            servers.sort(key=lambda s: s.id)

            for server in servers:
                marker = "  "
                click.echo(f"{marker}{server.in_list_str()}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@server.command(name="add")
@click.argument("link")
@click.option("--name", help="Custom server name")
def server_add(link: str, name: str | None):
    """Add a server from proxy link."""
    try:
        protocol = BaseParser.detect_protocol(link)

        if protocol == "vless":
            parser = VLESSParser()
        elif protocol == "vmess":
            parser = VMessParser()
        else:
            click.echo(f"Error: Unsupported protocol: {protocol}")
            sys.exit(1)

        server = parser.parse(link)

        # Override name if provided
        if name:
            server.name = name

        config_mgr = ConfigManager()
        config_mgr.add_server(server)

        click.echo(f"Added server: {server.name}")
        click.echo(f"Protocol: {server.protocol}")
        click.echo(f"Address: {server.address}:{server.port}")
        click.echo(f"ID: {server.id}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@server.command(name="remove")
@click.argument("server_id", type=int)
def server_remove(server_id: int):
    try:
        config_mgr = ConfigManager()
        process_mgr = ProcessManager()

        server = config_mgr.get_server(server_id)
        if not server:
            click.echo(f"Error: Server {server_id} not found")
            sys.exit(1)

        # Проверяем, запущен ли сервер
        status = process_mgr.get_instance_status(server_id)
        if status["running"]:
            click.echo("Error: Cannot remove a running server. Stop it first.")
            sys.exit(1)

        config_mgr.remove_server(server.id)
        click.echo(f"Removed server: {server.name}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@server.command(name="test")
@click.argument("server_id", required=False)
@click.option("--timeout", default=5, help="Connection timeout in seconds")
def server_test(server_id: str | None, timeout: int):
    """Test server latency."""
    try:
        config_mgr = ConfigManager()
        from src.utils.latency import test_multiple_servers_sync, test_server_sync

        if server_id:
            # Test single server
            server = config_mgr.get_server(server_id)
            if not server:
                server = config_mgr.find_server_by_name(server_id)

            if not server:
                click.echo(f"Error: Server '{server_id}' not found")
                sys.exit(1)

            click.echo(f"Testing {server.name}...")
            result = test_server_sync(server, timeout=timeout)

            if result["status"] == "ok":
                click.echo(f"Latency: {result['latency_ms']} ms")
            else:
                click.echo("Connection timeout")

        else:
            # Test all servers
            servers = config_mgr.list_servers()

            if not servers:
                click.echo("No servers to test")
                sys.exit(0)

            click.echo(f"Testing {len(servers)} servers...\n")
            results = test_multiple_servers_sync(servers, timeout=timeout)

            # Sort by latency (put timeouts at the end)
            results.sort(
                key=lambda r: r["latency_ms"] if r["latency_ms"] is not None else 999999
            )

            for result in results:
                name = result["server_name"]
                address = f"{result['address']}:{result['port']}"

                if result["status"] == "ok":
                    latency = f"{result['latency_ms']} ms"
                    click.echo(f"{name:30} {address:25} {latency}")
                else:
                    click.echo(f"{name:30} {address:25} TIMEOUT")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@server.command(name="show")
@click.argument("server_id")
def server_show(server_id: str):
    """Show detailed server information."""
    try:
        config_mgr = ConfigManager()

        # Try to interpret as integer ID first
        try:
            sid = int(server_id)
            server = config_mgr.get_server(sid)
        except ValueError:
            server = None

        if not server:
            server = config_mgr.find_server_by_name(server_id)

        if not server:
            click.echo(f"Error: Server '{server_id}' not found")
            sys.exit(1)

        click.echo(f"Name: {server.name}")
        click.echo(f"ID: {server.id}")
        click.echo(f"Protocol: {server.protocol}")
        click.echo(f"Address: {server.address}:{server.port}")
        click.echo(f"UUID: {server.uuid}")

        if server.alter_id is not None:
            click.echo(f"Alter ID: {server.alter_id}")
        if server.flow:
            click.echo(f"Flow: {server.flow}")
        if server.network:
            click.echo(f"Network: {server.network}")
        if server.security:
            click.echo(f"Security: {server.security}")
        if server.sni:
            click.echo(f"SNI: {server.sni}")
        if server.path:
            click.echo(f"Path: {server.path}")
        if server.host:
            click.echo(f"Host: {server.host}")
        if server.public_key:
            click.echo(f"Public Key: {server.public_key}")
        if server.subscription:
            click.echo(f"Subscription: {server.subscription}")
        click.echo(f"Added: {server.added_at}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
