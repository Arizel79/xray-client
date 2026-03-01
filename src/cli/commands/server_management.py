"""Server management commands for xray-client CLI."""

import sys

import click

from src.services.xray_service import XrayService
from src.utils.latency import test_multiple_servers_sync, test_server_sync


@click.group()
def server():
    """Manage servers."""
    pass

@server.command(name="list")
@click.option(
    "-n",
    "--no-subscription-sorting",
    is_flag=True,
    help="Don't group servers by subscription",
)
def server_list(no_subscription_sorting):
    try:
        service = XrayService()
        servers = service.list_servers()
        if not servers:
            click.echo("No servers configured")
            sys.exit(0)

        if not no_subscription_sorting:
            grouped_data = service.get_servers_grouped_by_subscription()
            grouped = grouped_data["grouped"]
            standalone = grouped_data["standalone"]

            # Получаем URL подписок для отображения
            subs = {sub.name: sub.url for sub in service.list_subscriptions()}

            for sub_name, sub_servers in grouped.items():
                url = subs.get(sub_name, "URL not found")
                click.echo(f'Subscription "{sub_name}" ({url}):')
                for server in sub_servers:
                    click.echo(f"  {server.in_list_str()}")
                click.echo()

            if standalone:
                click.echo("Servers (without subscription):")
                for server in standalone:
                    click.echo(f"  {server.in_list_str()}")
                click.echo()
        else:
            servers.sort(key=lambda s: s.id)
            for server in servers:
                click.echo(f"  {server.in_list_str()}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@server.command(name="add")
@click.argument("link")
@click.option("--name", help="Custom server name")
def server_add(link: str, name: str | None):
    """Add a server from proxy link."""
    try:
        service = XrayService()
        server = service.add_server_from_link(link, name)
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
    """Remove a server by ID."""
    try:
        service = XrayService()
        server = service.get_server(server_id)
        if not server:
            click.echo(f"Error: Server {server_id} not found")
            sys.exit(1)

        # Проверка на запущенный сервер уже внутри remove_server
        if service.remove_server(server_id):
            click.echo(f"Removed server: {server.name}")
        else:
            click.echo(f"Failed to remove server {server_id}")

    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@server.command(name="test")
@click.argument("server_id", required=False)
@click.option("--timeout", default=5, help="Connection timeout in seconds")
def server_test(server_id: str | None, timeout: int):
    """Test server latency."""
    try:
        service = XrayService()

        if server_id:
            # Test single server
            try:
                sid = int(server_id)
                server = service.get_server(sid)
            except ValueError:
                server = service.find_server_by_name(server_id)

            if not server:
                click.echo(f"Error: Server '{server_id}' not found")
                sys.exit(1)

            click.echo(f"Testing {server.name}...")
            result = service.test_server_latency(server.id, timeout)

            if result["status"] == "ok":
                click.echo(f"Latency: {result['latency_ms']} ms")
            else:
                click.echo("Connection timeout")
        else:
            servers = service.list_servers()
            if not servers:
                click.echo("No servers to test")
                sys.exit(0)

            click.echo(f"Testing {len(servers)} servers...\n")
            
            results = service.test_all_servers_latency(timeout)

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
        service = XrayService()

        try:
            sid = int(server_id)
            server = service.get_server(sid)
        except ValueError:
            server = service.find_server_by_name(server_id)

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