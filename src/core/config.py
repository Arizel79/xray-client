"""Configuration management for xray-client."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server configuration model."""

    id: int = Field(default_factory=lambda: 0)
    name: str
    protocol: str  # vless, vmess, trojan, shadowsocks
    address: str
    port: int
    uuid: str
    # Optional fields
    flow: Optional[str] = None
    network: str = "tcp"  # tcp, ws, grpc, http, quic
    security: str = "none"  # none, tls, xtls, reality
    sni: Optional[str] = None
    alpn: Optional[str] = None
    fingerprint: Optional[str] = None
    # Transport settings
    path: Optional[str] = None
    host: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    # REALITY specific
    public_key: Optional[str] = None
    short_id: Optional[str] = None
    spider_x: Optional[str] = None
    # Metadata
    subscription: Optional[str] = None  # Name of subscription this server belongs to
    added_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


    # VMess specific
    alter_id: Optional[int] = None

    def __str__(self) -> str:
        """String representation of server."""
        return f"{self.name} ({self.protocol}://{self.address}:{self.port})"

class RunningInstance(BaseModel):
    """Модель запущенного экземпляра Xray"""
    instance_id: str
    server_id: int
    pid: int
    start_time: str
    config_path: str
    listen_host: str = "127.0.0.1"
    listen_socks_port: Optional[int] = None 
    listen_http_port: Optional[int] = None 
    status: str = "running"  # 'running', 'stopped', 'error'

class Subscription(BaseModel):
    """Subscription configuration model."""

    name: str
    url: str
    last_update: Optional[str] = None
    enabled: bool = True

    def __str__(self) -> str:
        """String representation of subscription."""
        return f"{self.name} ({self.url[:50]}...)"


class Settings(BaseModel):
    """Application settings model."""

    listen_host: str = "127.0.0.1"
    listen_socks_port: int = 1080
    listen_http_port: int = 1081

    auto_update_subscriptions: bool = True
    update_interval_hours: int = 24
    log_level: str = "warning"

    # Subscriptions headers
    subscription_headers_enable: bool = False
    subscription_headers: Dict[str, str] = Field(default_factory=dict)


class Config(BaseModel):
    """Main configuration model."""

    version: str = "1.0"
    current_server: Optional[str] = None
    servers: List[ServerConfig] = Field(default_factory=list)
    subscriptions: List[Subscription] = Field(default_factory=list)
    settings: Settings = Field(default_factory=Settings)


class ConfigManager:
    """Manages configuration file operations."""

    def __init__(self, config_dir: Path | None = None):
        """Initialize config manager.

        Args:
            config_dir: Configuration directory (default: ~/.xray-client)
        """
        self.config_dir = config_dir or Path.home() / ".xray-client"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Config:
        """Load configuration from file.

        Returns:
            Config object

        Creates default config if file doesn't exist.
        """
        if not self.config_file.exists():
            return Config()

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Config(**data)
        except Exception as e:
            print(f"Warning: Failed to load config: {e}. Using default config.")
            return Config()

    def save(self, config: Config) -> None:
        """Save configuration to file.

        Args:
            config: Config object to save

        Uses atomic write (temp file + rename) for safety.
        """
        temp_file = self.config_file.with_suffix(".tmp")

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.rename(self.config_file)

        except Exception as e:
            temp_file.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to save config: {e}")

    def add_server(self, server: ServerConfig) -> None:
        """Add a server to configuration.

        Args:
            server: Server configuration to add
        """
        config = self.load()

        # Generate new numeric ID (всегда, даже если ID уже был)
        if config.servers:
            # Найти максимальный ID и добавить 1
            max_id = max(s.id for s in config.servers)
            server.id = max_id + 1
        else:
            server.id = 1  # Первый сервер

        config.servers.append(server)
        self.save(config)
        
    def remove_server(self, server_id: str) -> bool:
        """Remove a server from configuration.

        Args:
            server_id: ID of server to remove

        Returns:
            True if server was removed, False if not found
        """
        config = self.load()
        original_count = len(config.servers)

        config.servers = [s for s in config.servers if s.id != server_id]

        if len(config.servers) < original_count:
            # If removed server was current, clear current_server
            if config.current_server == server_id:
                config.current_server = None

            self.save(config)
            return True

        return False

    def get_server(self, server_id: str) -> Optional[ServerConfig]:
        """Get server by ID.

        Args:
            server_id: Server ID

        Returns:
            Server configuration or None if not found
        """
        config = self.load()
        for server in config.servers:
            if server.id == server_id:
                return server
        return None

    def find_server_by_name(self, name: str) -> Optional[ServerConfig]:
        """Find server by name (case-insensitive).

        Args:
            name: Server name

        Returns:
            Server configuration or None if not found
        """
        config = self.load()
        name_lower = name.lower()
        for server in config.servers:
            if server.name.lower() == name_lower:
                return server
        return None

    def list_servers(self) -> List[ServerConfig]:
        """List all servers.

        Returns:
            List of server configurations
        """
        config = self.load()
        return config.servers

    def add_subscription(self, subscription: Subscription) -> None:
        """Add a subscription.

        Args:
            subscription: Subscription to add

        Raises:
            ValueError: If subscription with same name exists
        """
        config = self.load()

        # Check for duplicate name
        if any(sub.name == subscription.name for sub in config.subscriptions):
            raise ValueError(f"Subscription '{subscription.name}' already exists")

        config.subscriptions.append(subscription)
        self.save(config)

    def remove_subscription(self, name: str, remove_servers: bool = True) -> bool:
        """Remove a subscription.

        Args:
            name: Subscription name
            remove_servers: Also remove servers from this subscription

        Returns:
            True if subscription was removed
        """
        config = self.load()
        original_count = len(config.subscriptions)

        config.subscriptions = [s for s in config.subscriptions if s.name != name]

        if len(config.subscriptions) < original_count:
            if remove_servers:
                # Remove servers from this subscription
                config.servers = [s for s in config.servers if s.subscription != name]

            self.save(config)
            return True

        return False

    def get_subscription(self, name: str) -> Optional[Subscription]:
        """Get subscription by name.

        Args:
            name: Subscription name

        Returns:
            Subscription or None if not found
        """
        config = self.load()
        for sub in config.subscriptions:
            if sub.name == name:
                return sub
        return None

    def list_subscriptions(self) -> List[Subscription]:
        """List all subscriptions.

        Returns:
            List of subscriptions
        """
        config = self.load()
        return config.subscriptions

    def update_subscription_servers(
        self, subscription_name: str, servers: List[ServerConfig]
    ) -> None:
        """Update servers for a subscription.

        Removes old servers from this subscription and adds new ones.

        Args:
            subscription_name: Name of subscription
            servers: New servers to add
        """
        config = self.load()

        # Remove old servers from this subscription
        config.servers = [
            s for s in config.servers if s.subscription != subscription_name
        ]

        # Add new servers
        for server in servers:
            if config.servers:
                max_id = max(s.id for s in config.servers)
                server.id = max_id + 1
            else:
                server.id = 1

        # Update subscription last_update
        for sub in config.subscriptions:
            if sub.name == subscription_name:
                sub.last_update = datetime.utcnow().isoformat()
                break

        self.save(config)

    def set_current_server(self, server_id: Optional[str]) -> None:
        """Set current active server.

        Args:
            server_id: Server ID or None to clear
        """
        config = self.load()
        config.current_server = server_id
        self.save(config)

    def get_current_server(self) -> Optional[ServerConfig]:
        """Get current active server.

        Returns:
            Current server configuration or None
        """
        config = self.load()
        if config.current_server:
            try:
                server_id = int(config.current_server)
                return self.get_server(server_id)
            except ValueError:
                return None
        return None
