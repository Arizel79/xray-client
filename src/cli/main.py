"""Main CLI interface for xray-client."""

import sys
from pathlib import Path

import click

from src.core.binary_manager import BinaryManager
from src.core.config import ConfigManager, ServerConfig, Subscription
from src.core.config_generator import ConfigGenerator
from src.core.process_manager import ProcessManager
from src.core.subscription import SubscriptionManager
from src.parsers.base import BaseParser
from src.parsers.vless import VLESSParser
from src.parsers.vmess import VMessParser
from src.utils.helpers import format_timestamp, format_uptime, truncate_string
from src.utils.latency import test_multiple_servers_sync, test_server_sync


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """XRAY Client - Python CLI for VLESS VPN with subscription support."""
    pass


@cli.command()
@click.argument("server_name_or_id")
def connect(server_name_or_id: str):
    """Connect to a server by name or ID."""
    try:
        config_mgr = ConfigManager()
        binary_mgr = BinaryManager()
        process_mgr = ProcessManager()

        # Check if already running
        if process_mgr.is_running():
            click.echo("Already connected. Disconnect first or use reconnect.")
            sys.exit(1)

        # Find server
        server = config_mgr.get_server(server_name_or_id)
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
        config_mgr.set_current_server(server.id)

        click.echo(f"Connected to {server.name}")
        click.echo(f"SOCKS5: 127.0.0.1:{config.settings.local_socks_port}")
        click.echo(f"HTTP: 127.0.0.1:{config.settings.local_http_port}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
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


@cli.command()
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
        click.echo(f"SOCKS5: 127.0.0.1:{config.settings.local_socks_port}")
        click.echo(f"HTTP: 127.0.0.1:{config.settings.local_http_port}")

        click.echo(f"\nProcess Info:")
        click.echo(f"  PID: {status['pid']}")
        click.echo(f"  Uptime: {format_uptime(status['uptime'])}")
        click.echo(f"  Memory: {status['memory_mb']} MB")
        click.echo(f"  CPU: {status['cpu_percent']}%")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--sort-by", type=click.Choice(["name", "protocol", "subscription"]), default="name"
)
def list(sort_by: str):
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


@cli.command()
@click.argument("link")
@click.option("--name", help="Custom server name")
def add(link: str, name: str | None):
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


@cli.command()
@click.argument("server_id")
def remove(server_id: str):
    """Remove a server by ID."""
    try:
        config_mgr = ConfigManager()

        # Get server info before removing
        server = config_mgr.get_server(server_id)
        if not server:
            click.echo(f"Error: Server '{server_id}' not found")
            sys.exit(1)

        # Check if currently connected
        current = config_mgr.get_current_server()
        if current and current.id == server_id:
            click.echo(
                "Error: Cannot remove currently connected server. Disconnect first."
            )
            sys.exit(1)

        # Remove server
        config_mgr.remove_server(server_id)
        click.echo(f"Removed server: {server.name}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
def subscribe():
    """Manage subscriptions."""
    pass


@subscribe.command(name="add")
@click.argument("name")
@click.argument("url")
def subscribe_add(name: str, url: str):
    """Add a subscription."""
    try:
        config_mgr = ConfigManager()

        subscription = Subscription(name=name, url=url)
        config_mgr.add_subscription(subscription)

        click.echo(f"Added subscription: {name}")
        click.echo(f"URL: {truncate_string(url, 60)}")
        click.echo("\nRun 'xray-client subscribe update' to fetch servers")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@subscribe.command(name="update")
@click.argument("name", required=False)
def subscribe_update(name: str | None):
    """Update subscription(s)."""
    try:
        config_mgr = ConfigManager()
        sub_mgr = SubscriptionManager()
        
        # Load config to get HWID settings
        config = config_mgr.load()
        hwid_enabled = config.settings.enable_hwid
        hwid = config.settings.hwid if hwid_enabled else None

        # Get subscriptions to update
        if name:
            subscription = config_mgr.get_subscription(name)
            if not subscription:
                click.echo(f"Error: Subscription '{name}' not found")
                sys.exit(1)
            subscriptions = [subscription]
        else:
            subscriptions = config_mgr.list_subscriptions()

        if not subscriptions:
            click.echo("No subscriptions configured")
            sys.exit(0)

        # Update each subscription
        for sub in subscriptions:
            click.echo(f"Updating subscription: {sub.name}...")
            
            if hwid_enabled:
                click.echo(f"  Using HWID header: {hwid}")

            try:
                servers = sub_mgr.update_subscription(
                    sub.url, 
                    hwid_enabled=hwid_enabled, 
                    hwid=hwid
                )
                click.echo(f"  Found {len(servers)} servers")

                # Update config
                config_mgr.update_subscription_servers(sub.name, servers)
                click.echo(f"  Updated successfully")

            except Exception as e:
                click.echo(f"  Error: {e}", err=True)
                continue

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@subscribe.command(name="list")
def subscribe_list():
    """List all subscriptions."""
    try:
        config_mgr = ConfigManager()
        subscriptions = config_mgr.list_subscriptions()

        if not subscriptions:
            click.echo("No subscriptions configured")
            sys.exit(0)

        click.echo(f"Total subscriptions: {len(subscriptions)}\n")

        for sub in subscriptions:
            click.echo(f"Name: {sub.name}")
            click.echo(f"URL: {truncate_string(sub.url, 70)}")
            click.echo(f"Last Update: {format_timestamp(sub.last_update)}")
            click.echo(f"Enabled: {sub.enabled}")
            click.echo()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@subscribe.command(name="remove")
@click.argument("name")
@click.option(
    "--keep-servers", is_flag=True, help="Keep servers from this subscription"
)
def subscribe_remove(name: str, keep_servers: bool):
    """Remove a subscription."""
    try:
        config_mgr = ConfigManager()

        if not config_mgr.get_subscription(name):
            click.echo(f"Error: Subscription '{name}' not found")
            sys.exit(1)

        config_mgr.remove_subscription(name, remove_servers=not keep_servers)

        click.echo(f"Removed subscription: {name}")
        if not keep_servers:
            click.echo("All servers from this subscription were also removed")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("server_id", required=False)
@click.option("--timeout", default=5, help="Connection timeout in seconds")
def test(server_id: str | None, timeout: int):
    """Test server latency."""
    try:
        config_mgr = ConfigManager()

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


@cli.group()
def hwid():
    pass


@hwid.command(name="enable")
def hwid_enable():
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
        
        config.settings.enable_hwid = True
        config_mgr.save(config)
        
        click.echo("HWID enabled")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@hwid.command(name="disable")
def hwid_disable():
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
        
        config.settings.enable_hwid = False
        config_mgr.save(config)
        
        click.echo("HWID disabled")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@hwid.command(name="set")
@click.argument("hwid")
def hwid_set(hwid: str):
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
        
        config.settings.hwid = hwid
        config_mgr.save(config)
        
        click.echo(f"HWID string set to: {hwid}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@hwid.command(name="status")
def hwid_status():
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
        
        if config.settings.enable_hwid:
            click.echo("HWID: enabled")
        else:
            click.echo("HWID: disabled")
        if config.settings.hwid:
            click.echo(f"HWID string: {config.settings.hwid}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


