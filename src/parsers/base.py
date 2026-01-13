"""Base parser class for proxy links."""

from abc import ABC, abstractmethod

from src.core.config import ServerConfig


class BaseParser(ABC):
    """Base class for proxy link parsers."""

    @abstractmethod
    def parse(self, link: str) -> ServerConfig:
        """Parse proxy link to ServerConfig.

        Args:
            link: Proxy link (e.g., vless://..., vmess://...)

        Returns:
            ServerConfig object

        Raises:
            ValueError: If link format is invalid
        """
        pass

    @staticmethod
    def detect_protocol(link: str) -> str | None:
        """Detect protocol from link.

        Args:
            link: Proxy link

        Returns:
            Protocol name or None if not recognized
        """
        link = link.strip()
        if link.startswith("vless://"):
            return "vless"
        elif link.startswith("vmess://"):
            return "vmess"
        elif link.startswith("trojan://"):
            return "trojan"
        elif link.startswith("ss://"):
            return "shadowsocks"
        return None
