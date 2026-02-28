"""Server management commands for xray-client CLI."""

import click
import sys

from src.core.config import ConfigManager
from src.parsers.base import BaseParser
from src.parsers.vless import VLESSParser
from src.parsers.vmess import VMessParser


@click.group()
def server():
    """Manage servers."""
    pass


@server.command(name="list")
@click.option(
    "--sort-by", type=click.Choice(["name", "protocol", "subscription"]), default="name"
)
def server_list(sort_by: str):
    """List all servers."""
    try:
        config_mgr = ConfigManager()
        servers = config_mgr.list_servers()

        if not servers:
            click.echo("No servers configured")
            sys.exit(0)

        # Sort servers
        if sort_by == "name":
            servers.sort(key=lambda s: s.name.lower())
        elif sort_by == "protocol":
            servers.sort(key=lambda s: s.protocol)
        elif sort_by == "subscription":
            servers.sort(key=lambda s: s.subscription or "")

        current = config_mgr.get_current_server()
        current_id = current.id if current else None

        click.echo(f"Total servers: {len(servers)}\n")

        for server in servers:
            marker = "* " if server.id == current_id else "  "
            sub_info = f" [{server.subscription}]" if server.subscription else ""
            click.echo(
                f"{marker}{server.name:30} {server.protocol:8} "
                f"{server.address}:{server.port}{sub_info}"
            )
            click.echo(f"   ID: {server.id}")

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
@click.argument("server_id")
def server_remove(server_id: str):
    """Remove a server by ID."""
    try:
        config_mgr = ConfigManager()

        # Get server info before removing
        server = config_mgr.get_server(server_id)
        if not server:
            server = config_mgr.find_server_by_name(server_id)
            
        if not server:
            click.echo(f"Error: Server '{server_id}' not found")
            sys.exit(1)

        # Check if currently connected
        current = config_mgr.get_current_server()
        if current and current.id == server.id:
            click.echo(
                "Error: Cannot remove currently connected server. Disconnect first."
            )
            sys.exit(1)

        # Remove server
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

        server = config_mgr.get_server(server_id)
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