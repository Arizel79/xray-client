"""VLESS link parser."""

from urllib.parse import parse_qs, unquote, urlparse

from src.core.config import ServerConfig
from src.parsers.base import BaseParser


class VLESSParser(BaseParser):
    """Parser for VLESS protocol links.

    Format: vless://UUID@HOST:PORT?params#name
    """

    def parse(self, link: str) -> ServerConfig:
        """Parse VLESS link to ServerConfig.

        Args:
            link: VLESS link (vless://uuid@host:port?params#name)

        Returns:
            ServerConfig object

        Raises:
            ValueError: If link format is invalid
        """
        if not link.startswith("vless://"):
            raise ValueError("Invalid VLESS link: must start with vless://")

        try:
            # Parse URL
            parsed = urlparse(link)

            # Extract UUID (username part)
            uuid_str = parsed.username
            if not uuid_str:
                raise ValueError("UUID not found in VLESS link")

            # Extract host and port
            host = parsed.hostname
            port = parsed.port

            if not host:
                raise ValueError("Host not found in VLESS link")
            if not port:
                raise ValueError("Port not found in VLESS link")

            # Extract name from fragment (after #)
            name = unquote(parsed.fragment) if parsed.fragment else f"{host}:{port}"

            # Parse query parameters
            params = parse_qs(parsed.query)

            # Extract common parameters (take first value if list)
            def get_param(key: str, default=None):
                values = params.get(key, [])
                return values[0] if values else default

            # Network type (tcp, ws, grpc, http, quic)
            network = get_param("type", "tcp")

            # Security (none, tls, xtls, reality)
            security = get_param("security", "none")

            # Server Name Indication
            sni = get_param("sni")

            # Flow control (for XTLS)
            flow = get_param("flow")

            # Encryption (should be "none" for VLESS)
            encryption = get_param("encryption", "none")

            # ALPN
            alpn = get_param("alpn")

            # Fingerprint
            fingerprint = get_param("fp") or get_param("fingerprint")

            # Transport settings
            path = get_param("path")
            host_header = get_param("host")

            # REALITY specific parameters
            public_key = get_param("pbk")
            short_id = get_param("sid")
            spider_x = get_param("spx")

            # Build headers dict if host is present
            headers = None
            if host_header:
                headers = {"Host": host_header}

            # Create ServerConfig
            server = ServerConfig(
                name=name,
                protocol="vless",
                address=host,
                port=port,
                uuid=uuid_str,
                flow=flow,
                network=network,
                security=security,
                sni=sni,
                alpn=alpn,
                fingerprint=fingerprint,
                path=path,
                host=host_header,
                headers=headers,
                public_key=public_key,
                short_id=short_id,
                spider_x=spider_x,
            )

            return server

        except Exception as e:
            raise ValueError(f"Failed to parse VLESS link: {e}")


def parse_vless(link: str) -> ServerConfig:
    """Convenience function to parse VLESS link.

    Args:
        link: VLESS link

    Returns:
        ServerConfig object
    """
    parser = VLESSParser()
    return parser.parse(link)
