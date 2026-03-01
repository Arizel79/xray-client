"""Connection commands for xray-client CLI."""

import socket
import sys

import click

from src.services.xray_service import XrayService
from src.utils.helpers import format_uptime


@click.group()
def connection():
    """Manage connections to servers."""
    pass


@connection.command(name="start")
@click.argument("server_id", type=int)
@click.option("--listen-host", default="127.0.0.1", help="Host to listen on")
@click.option("--socks-port", type=int, help="SOCKS5 port (omit to disable SOCKS5)")
@click.option("--http-port", type=int, help="HTTP port (omit to disable HTTP)")
@click.option("--force", is_flag=True, help="Force start even if port is in use")
def connection_start(
    server_id: int,
    listen_host: str,
    socks_port: int | None,
    http_port: int | None,
    force: bool,
):
    """Start connection to a specific server."""
    try:
        service = XrayService()

        # Find server
        server = service.get_server(server_id)
        if not server:
            click.echo(f"Error: Server {server_id} not found")
            sys.exit(1)

        # Check if this server is already running
        status = service.get_server_status(server_id)
        if status["running"]:
            click.echo(
                f"Error: Server {server_id} is already running (PID: {status['pid']})"
            )
            sys.exit(1)

        # Load settings to get default ports
        settings = service.get_settings()

        # Determine which proxies to enable
        use_socks = socks_port is not None
        use_http = http_port is not None

        # If both ports omitted, use both defaults
        if not use_socks and not use_http:
            use_socks = True
            use_http = True
            socks_port = settings.listen_socks_port
            http_port = settings.listen_http_port
        else:
            # Use provided ports or defaults if omitted but enabled
            if use_socks and socks_port is None:
                socks_port = settings.listen_socks_port
            if use_http and http_port is None:
                http_port = settings.listen_http_port

        # Check port availability
        if not force:
            occupied = service.check_ports_availability(
                listen_host,
                socks_port if use_socks else None,
                http_port if use_http else None
            )
            if occupied:
                click.echo(f"Error: Port(s) {', '.join(occupied)} on {listen_host} are already in use")
                sys.exit(1)


        # Start instance
        click.echo(f"Starting connection to {server.name}...")
        instance_id = service.start_server(
            server_id,
            listen_host=listen_host,
            socks_port=socks_port if use_socks else None,
            http_port=http_port if use_http else None,
        )

        new_status = service.get_server_status(server_id)

        click.echo(f"Connected to {server.name}")

        if use_socks:
            click.echo(f"   SOCKS5: {listen_host}:{socks_port}")
        if use_http:
            click.echo(f"   HTTP: {listen_host}:{http_port}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@connection.command(name="stop")
@click.argument("server_id", type=int)
def connection_stop(server_id: int):
    """Stop connection to a specific server."""
    try:
        service = XrayService()

        status = service.get_server_status(server_id)
        if not status["running"]:
            click.echo(f"Server {server_id} is not running")
            sys.exit(0)

        click.echo(f"Stopping connection to server {server_id}...")
        if service.stop_server(server_id):
            click.echo(f"   Stopped connection to server {server_id}")
        else:
            click.echo(f"Failed to stop server {server_id}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@connection.command(name="status")
@click.argument("server_id", type=int, required=False)
def connection_status(server_id: int | None):
    """Show status of connections."""
    try:
        service = XrayService()

        def print_server(server, status):
            if status["running"]:
                click.echo(f"{server}: running")
                click.echo(f"  PID: {status['pid']}")
                click.echo(f"  Uptime: {format_uptime(status['uptime'])}")
                click.echo(f"  Memory: {status['memory_mb']} MB")
                click.echo(f"  CPU: {status['cpu_percent']}%")

                if status["socks_port"]:
                    click.echo(
                        f"  SOCKS5 proxy: {status['listen_host']}:{status['socks_port']}"
                    )
                else:
                    click.echo("  SOCKS5 proxy: disabled")

                if status["http_port"]:
                    click.echo(
                        f"  HTTP proxy: {status['listen_host']}:{status['http_port']}"
                    )
                else:
                    click.echo("  HTTP proxy: disabled")
            else:
                click.echo(f"{server}: stopped")

        if server_id is not None:
            server = service.get_server(server_id)
            if not server:
                click.echo(f"Error: Server {server_id} not found")
                sys.exit(1)

            status = service.get_server_status(server_id)
            print_server(server, status)
        else:
            instances = service.list_running_instances()
            if not instances:
                click.echo("No running connections")
                sys.exit(0)

            click.echo(f"Running connections: {len(instances)}\n")
            for inst in instances:
                server = service.get_server(inst["server_id"])
                if server:
                    status = service.get_server_status(server.id)
                    print_server(server, status)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@connection.command(name="list")
def connection_list():
    """Alias for 'connection status' without arguments."""
    connection_status(None)


@connection.command(name="logs")
@click.argument("server_id", type=int)
@click.option("--lines", "-n", default=50, help="Number of lines to show")
@click.option("--error", "-e", is_flag=True, help="Show error log instead of stdout")
def connection_logs(server_id: int, lines: int, error: bool):
    """Show logs for a specific connection."""
    try:
        service = XrayService()

        server = service.get_server(server_id)
        if not server:
            click.echo(f"Error: Server {server_id} not found")
            sys.exit(1)

        logs = service.get_server_logs(server_id, lines, error)

        if not logs:
            click.echo("No logs available")
            sys.exit(0)

        log_type = "error" if error else "output"
        click.echo(f"=== {server.name} ({log_type} log, last {lines} lines) ===\n")
        click.echo(logs)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@connection.command(name="stop-all")
def connection_stop_all():
    """Stop all running connections."""
    try:
        service = XrayService()
        instances = service.list_running_instances()

        if not instances:
            click.echo("No running connections")
            sys.exit(0)

        click.echo(f"Stopping {len(instances)} connections...")
        count = service.stop_all_servers()

        click.echo(f"✅ Stopped {count} connections")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)