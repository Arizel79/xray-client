from typing import List, Optional, Dict, Any

from src.core.config import ServerConfig, Subscription
from src.core.config_generator import ConfigGenerator
from src.parsers.base import BaseParser
from src.parsers.vless import VLESSParser
from src.parsers.vmess import VMessParser


class ServerMixin:
    """Mixin for server-related operations."""

    def list_servers(self) -> List[ServerConfig]:
        return self.config_mgr.list_servers()

    def get_server(self, server_id: int) -> Optional[ServerConfig]:
        return self.config_mgr.get_server(server_id)

    def find_server_by_name(self, name: str) -> Optional[ServerConfig]:
        return self.config_mgr.find_server_by_name(name)

    def add_server_from_link(self, link: str, name: Optional[str] = None) -> ServerConfig:
        protocol = BaseParser.detect_protocol(link)
        if protocol == "vless":
            parser = VLESSParser()
        elif protocol == "vmess":
            parser = VMessParser()
        else:
            raise ValueError(f"Unsupported protocol: {protocol}")
        server = parser.parse(link)
        if name:
            server.name = name
        self.config_mgr.add_server(server)
        return server

    def remove_server(self, server_id: int) -> bool:
        status = self.process_mgr.get_instance_status(server_id)
        if status["running"]:
            raise RuntimeError("Cannot remove a running server")
        return self.config_mgr.remove_server(server_id)

    def get_server_status(self, server_id: int) -> Dict[str, Any]:
        return self.process_mgr.get_instance_status(server_id)

    def get_all_servers_status(self) -> Dict[int, Dict[str, Any]]:
        servers = self.list_servers()
        return {s.id: self.get_server_status(s.id) for s in servers}

    def start_server(self,
                     server_id: int,
                     listen_host: Optional[str] = None,
                     socks_port: Optional[int] = None,
                     http_port: Optional[int] = None) -> str:
        server = self.get_server(server_id)
        if not server:
            raise ValueError(f"Server {server_id} not found")

        config = self.config_mgr.load()
        settings = config.settings

        listen_host = listen_host or settings.listen_host
        socks_port = socks_port if socks_port is not None else settings.listen_socks_port
        http_port = http_port if http_port is not None else settings.listen_http_port

        xray_path = self.binary_mgr.ensure_binary()
        generator = ConfigGenerator(settings)
        xray_config = generator.generate_for_ports(
            server,
            listen_host=listen_host,
            socks_port=socks_port,
            http_port=http_port,
        )

        instance_id = self.process_mgr.start_instance(
            server_id,
            xray_path,
            xray_config,
            listen_host=listen_host,
            socks_port=socks_port,
            http_port=http_port,
        )
        return instance_id

    def stop_server(self, server_id: int, timeout: int = 5) -> bool:
        return self.process_mgr.stop_instance(server_id, timeout)

    def restart_server(self, server_id: int, timeout: int = 5) -> bool:
        return self.process_mgr.restart_instance(server_id, timeout)

    def get_server_logs(self, server_id: int, lines: int = 50, error: bool = False) -> str:
        return self.process_mgr.get_instance_logs(server_id, lines, error)


class SubscriptionMixin:
    """Mixin for subscription-related operations."""

    def list_subscriptions(self) -> List[Subscription]:
        return self.config_mgr.list_subscriptions()

    def get_subscription(self, name: str) -> Optional[Subscription]:
        return self.config_mgr.get_subscription(name)

    def add_subscription(self, name: str, url: str) -> None:
        sub = Subscription(name=name, url=url)
        self.config_mgr.add_subscription(sub)

    def remove_subscription(self, name: str, remove_servers: bool = True) -> bool:
        return self.config_mgr.remove_subscription(name, remove_servers)

    def update_subscription(self, name: str) -> List[ServerConfig]:
        config = self.config_mgr.load()
        sub = self.get_subscription(name)
        if not sub:
            raise ValueError(f"Subscription {name} not found")
        headers = config.settings.subscription_headers if config.settings.subscription_headers_enable else None
        servers = self.sub_mgr.update_subscription(sub.url, headers=headers)
        self.config_mgr.update_subscription_servers(name, servers)
        return servers

    def update_all_subscriptions(self) -> List[tuple]:
        """Update all enabled subscriptions. Returns list of (name, count, error)."""
        config = self.config_mgr.load()
        results = []
        for sub in config.subscriptions:
            if not sub.enabled:
                continue
            try:
                servers = self.update_subscription(sub.name)
                results.append((sub.name, len(servers), None))
            except Exception as e:
                results.append((sub.name, 0, str(e)))
        return results


class ProcessMixin:
    """Mixin for process management (running instances)."""

    def list_running_instances(self) -> List[Dict]:
        return self.process_mgr.list_running_instances()

    def stop_all_servers(self, timeout: int = 5) -> int:
        return self.process_mgr.stop_all(timeout)


class SettingsMixin:
    """Mixin for settings management."""

    def get_settings(self):
        return self.config_mgr.load().settings

    def update_settings(self, **kwargs):
        config = self.config_mgr.load()
        for key, value in kwargs.items():
            if hasattr(config.settings, key):
                setattr(config.settings, key, value)
        self.config_mgr.save(config)

    def set_subscription_header(self, key: str, value: str) -> None:
        config = self.config_mgr.load()
        config.settings.subscription_headers[key] = value
        self.config_mgr.save(config)

    def remove_subscription_header(self, key: str) -> bool:
        config = self.config_mgr.load()
        if key in config.settings.subscription_headers:
            del config.settings.subscription_headers[key]
            self.config_mgr.save(config)
            return True
        return False

    def clear_subscription_headers(self) -> None:
        config = self.config_mgr.load()
        config.settings.subscription_headers.clear()
        self.config_mgr.save(config)

    def set_subscription_headers_enabled(self, enabled: bool) -> None:
        config = self.config_mgr.load()
        config.settings.subscription_headers_enable = enabled
        self.config_mgr.save(config)