"""Subscription management for fetching and parsing server lists."""

import base64
from typing import List

import httpx

from src.core.config import ServerConfig
from src.parsers.base import BaseParser
from src.parsers.vless import VLESSParser
from src.parsers.vmess import VMessParser


class SubscriptionManager:
    """Manages subscription fetching and parsing."""

    def __init__(self):
        """Initialize subscription manager."""
        self.parsers = {
            "vless": VLESSParser(),
            "vmess": VMessParser(),
        }

    def fetch_subscription(self, url: str, timeout: int = 30) -> str:
        """Fetch subscription content from URL.

        Args:
            url: Subscription URL
            timeout: Request timeout in seconds

        Returns:
            Raw subscription content (base64-encoded text)

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.text

        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"
            )
        except httpx.TimeoutException:
            raise RuntimeError(f"Request timeout after {timeout} seconds")
        except httpx.RequestError as e:
            raise RuntimeError(f"Request failed: {e}")

    def decode_subscription(self, content: str) -> List[str]:
        """Decode base64-encoded subscription content.

        Args:
            content: Base64-encoded subscription content

        Returns:
            List of share links

        Raises:
            ValueError: If decoding fails
        """
        try:
            # Try to decode base64
            decoded = base64.b64decode(content).decode("utf-8")

            # Split by newlines and filter empty lines
            links = [line.strip() for line in decoded.split("\n") if line.strip()]

            return links

        except Exception as e:
            # If base64 decoding fails, maybe it's already plain text?
            # Try to split and see if we get valid links
            lines = [line.strip() for line in content.split("\n") if line.strip()]

            # Check if at least one line looks like a proxy link
            if any(
                line.startswith(("vless://", "vmess://", "trojan://", "ss://"))
                for line in lines
            ):
                return lines

            raise ValueError(f"Failed to decode subscription: {e}")

    def parse_links(self, links: List[str]) -> List[ServerConfig]:
        """Parse share links to ServerConfig objects.

        Args:
            links: List of share links

        Returns:
            List of ServerConfig objects (skips invalid links)
        """
        servers = []

        for link in links:
            try:
                protocol = BaseParser.detect_protocol(link)

                if protocol in self.parsers:
                    parser = self.parsers[protocol]
                    server = parser.parse(link)
                    servers.append(server)
                else:
                    print(f"Warning: Unsupported protocol in link: {link[:50]}...")

            except Exception as e:
                print(f"Warning: Failed to parse link: {e}")
                continue

        return servers

    def update_subscription(self, url: str) -> List[ServerConfig]:
        """Fetch and parse a subscription.

        Args:
            url: Subscription URL

        Returns:
            List of parsed ServerConfig objects

        Raises:
            RuntimeError: If fetch fails
            ValueError: If parsing fails
        """
        # Fetch subscription
        content = self.fetch_subscription(url)

        # Decode base64
        links = self.decode_subscription(content)

        # Parse links
        servers = self.parse_links(links)

        if not servers:
            raise ValueError("No valid servers found in subscription")

        return servers
