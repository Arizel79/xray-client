"""Subscription management for fetching and parsing server lists."""

import base64
from typing import Dict, List

import httpx

from src.core.config import ServerConfig
from src.parsers.base import BaseParser
from src.parsers.vless import VLESSParser
from src.parsers.vmess import VMessParser

from loguru import logger

class SubscriptionManager:
    """Manages subscription fetching and parsing."""

    def __init__(self):
        """Initialize subscription manager."""
        self.parsers = {
            "vless": VLESSParser(),
            "vmess": VMessParser(),
        }

    def fetch_subscription(
        self, url: str, timeout: int = 30, headers: Optional[Dict[str, str]] = None
    ) -> str:
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
            logger.info(f"Fetching subscription {url} with headers: {headers}")
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                logger.debug(f"Fetched, code: {response.status_code}")
                response.raise_for_status()
                return response.text

        except httpx.HTTPStatusError as e:
            err = f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"
            logger.error(err)
            raise RuntimeError(
                err
            )
        except httpx.TimeoutException:
            err = f"Request timeout after {timeout} seconds"
            logger.error(ferr)
            raise RuntimeError(err)
        except httpx.RequestError as e:
            err = f"Request failed: {e}"
            logger.error(err)
            raise RuntimeError(err)

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
            logger.debug(f"Decoding subscription content: {content}")
            # Try to decode base64
            decoded = base64.b64decode(content).decode("utf-8")

            # Split by newlines and filter empty lines
            links = [line.strip() for line in decoded.split("\n") if line.strip()]
            logger.debug(f"Decoded: {links}")

            return links

        except Exception as e:
            logger.warning(f"Decoding subscription content failed: {e}")

            # If base64 decoding fails, maybe it's already plain text?
            # Try to split and see if we get valid links
            logger.debug(f"Trying content as plain text")
            lines = [line.strip() for line in content.split("\n") if line.strip()]

            # Check if at least one line looks like a proxy link
            if any(
                line.startswith(("vless://", "vmess://", "trojan://", "ss://"))
                for line in lines
            ):
                logger.debug(f"Plain text seems like vpn link found")
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
                    logger.debug(f"Parsed server: {server}")
                    servers.append(server)
                else:
                    logger.warning(f"Unsupported protocol in link: {link}...")

            except Exception as e:
                logger.warning(f"Failed to parse link: {e}")
                continue

        logger.debug(f"Parsed {len(servers)} servers (from {len(links)})")
        return servers

    def update_subscription(
        self, url: str, headers: Optional[Dict[str, str]] = None
    ) -> List[ServerConfig]:
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
        content = self.fetch_subscription(url, headers=headers)

        # Decode base64
        links = self.decode_subscription(content)

        # Parse links
        servers = self.parse_links(links)

        if not servers:
            logger.info("No valid servers found in subscription")
            raise ValueError("No valid servers found in subscription")

        return servers
