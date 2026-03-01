"""Connection commands for xray-client CLI."""

import sys
import socket

import click

from src.core.binary_manager import BinaryManager
from src.core.config import ConfigManager
from src.core.config_generator import ConfigGenerator
from src.core.process_manager import ProcessManager
from src.utils.helpers import format_uptime


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except socket.error:
            return False


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
    force: bool
):
    """Start connection to a specific server."""
    try:
        config_mgr = ConfigManager()
        binary_mgr = BinaryManager()
        process_mgr = ProcessManager()

        # Find server
        server = config_mgr.get_server(server_id)
        if not server:
            click.echo(f"Error: Server {server_id} not found")
            sys.exit(1)

        # Check if this server is already running
        status = process_mgr.get_instance_status(server_id)
        if status["running"]:
            click.echo(f"Error: Server {server_id} is already running (PID: {status['pid']})")
            sys.exit(1)

        # Load config for settings (используем как значения по умолчанию)
        config = config_mgr.load()

        # Определяем какие прокси включать
        use_socks = socks_port is not None
        use_http = http_port is not None
        
        # Если оба порта не указаны, используем оба по умолчанию
        if not use_socks and not use_http:
            use_socks = True
            use_http = True
            socks_port = config.settings.listen_socks_port
            http_port = config.settings.listen_http_port
        else:
            # Используем указанные порты или значения по умолчанию
            if use_socks and socks_port is None:
                socks_port = config.settings.listen_socks_port
            if use_http and http_port is None:
                http_port = config.settings.listen_http_port

        # Проверяем доступность портов (только для включенных прокси)
        if not force:
            if use_socks and not is_port_available(socks_port, listen_host):
                click.echo(f"Error: SOCKS5 port {socks_port} on {listen_host} is already in use")
                sys.exit(1)
            if use_http and not is_port_available(http_port, listen_host):
                click.echo(f"Error: HTTP port {http_port} on {listen_host} is already in use")
                sys.exit(1)

        # Ensure binary is available
        xray_path = binary_mgr.ensure_binary()
        click.echo(f"Using xray binary: {xray_path}")

        # Generate config with custom settings
        config_gen = ConfigGenerator(config.settings)
        xray_config = config_gen.generate_for_ports(
            server, 
            listen_host=listen_host,
            socks_port=socks_port if use_socks else None,
            http_port=http_port if use_http else None
        )

        # Start instance
        click.echo(f"Starting connection to {server.name}...")
        instance_id = process_mgr.start_instance(
            server_id, 
            xray_path, 
            xray_config,
            listen_host=listen_host,
            socks_port=socks_port if use_socks else None,
            http_port=http_port if use_http else None
        )

        click.echo(f"✅ Connected to {server.name}")
        click.echo(f"   Instance ID: {instance_id}")
        
        # Показываем только включенные прокси
        if use_socks:
            click.echo(f"   SOCKS5: {listen_host}:{socks_port}")
        if use_http:
            click.echo(f"   HTTP: {listen_host}:{http_port}")
        if not use_socks and not use_http:
            click.echo(f"   ⚠️  No proxies enabled (SOCKS5 and HTTP are disabled)")
            
        click.echo(f"   PID: {process_mgr.get_instance_status(server_id)['pid']}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@connection.command(name="stop")
@click.argument("server_id", type=int)
def connection_stop(server_id: int):
    """Stop connection to a specific server."""
    try:
        process_mgr = ProcessManager()

        # Check if server is running
        status = process_mgr.get_instance_status(server_id)
        if not status["running"]:
            click.echo(f"Server {server_id} is not running")
            sys.exit(0)

        click.echo(f"Stopping connection to server {server_id}...")
        if process_mgr.stop_instance(server_id):
            click.echo(f"✅ Stopped connection to server {server_id}")
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
        process_mgr = ProcessManager()

        if server_id is not None:
            # Status for specific server
            status = process_mgr.get_instance_status(server_id)

            if status["running"]:
                click.echo(f"Server {server_id}: ✅ RUNNING")
                click.echo(f"  PID: {status['pid']}")
                click.echo(f"  Uptime: {format_uptime(status['uptime'])}")
                click.echo(f"  Memory: {status['memory_mb']} MB")
                click.echo(f"  CPU: {status['cpu_percent']}%")
                click.echo(f"  Listen host: {status['listen_host']}")
                
                if status['socks_port']:
                    click.echo(f"  SOCKS5: {status['listen_host']}:{status['socks_port']}")
                else:
                    click.echo(f"  SOCKS5: disabled")
                    
                if status['http_port']:
                    click.echo(f"  HTTP: {status['listen_host']}:{status['http_port']}")
                else:
                    click.echo(f"  HTTP: disabled")
            else:
                click.echo(f"Server {server_id}: ❌ STOPPED")

        else:
            # List all running instances
            instances = process_mgr.list_running_instances()

            if not instances:
                click.echo("No running connections")
                sys.exit(0)

            click.echo(f"Running connections: {len(instances)}\n")

            for inst in instances:
                click.echo(f"Server {inst['server_id']}:")
                click.echo(f"  PID: {inst['pid']}")
                click.echo(f"  Uptime: {format_uptime(inst['uptime'])}")
                click.echo(f"  Listen: {inst['listen_host']}")
                
                if inst['socks_port']:
                    click.echo(f"  SOCKS5: {inst['listen_host']}:{inst['socks_port']}")
                if inst['http_port']:
                    click.echo(f"  HTTP: {inst['listen_host']}:{inst['http_port']}")
                click.echo()

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
        process_mgr = ProcessManager()

        # Check if server exists
        config_mgr = ConfigManager()
        server = config_mgr.get_server(server_id)
        if not server:
            click.echo(f"Error: Server {server_id} not found")
            sys.exit(1)

        logs = process_mgr.get_instance_logs(server_id, lines, error)

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
        process_mgr = ProcessManager()
        instances = process_mgr.list_running_instances()

        if not instances:
            click.echo("No running connections")
            sys.exit(0)

        click.echo(f"Stopping {len(instances)} connections...")
        count = process_mgr.stop_all()

        click.echo(f"✅ Stopped {count} connections")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)