"""VMess link parser."""

import base64
import json

from src.core.config import ServerConfig
from src.parsers.base import BaseParser


class VMessParser(BaseParser):
    """Parser for VMess protocol links.

    Format: vmess://BASE64_ENCODED_JSON
    """

    def parse(self, link: str) -> ServerConfig:
        """Parse VMess link to ServerConfig.

        Args:
            link: VMess link (vmess://base64_json)

        Returns:
            ServerConfig object

        Raises:
            ValueError: If link format is invalid
        """
        if not link.startswith("vmess://"):
            raise ValueError("Invalid VMess link: must start with vmess://")

        try:
            # Extract base64 part
            b64_data = link[8:]  # Remove "vmess://"

            # Decode base64
            try:
                json_data = base64.b64decode(b64_data).decode("utf-8")
            except Exception:
                # Try with padding
                padding = 4 - len(b64_data) % 4
                if padding != 4:
                    b64_data += "=" * padding
                json_data = base64.b64decode(b64_data).decode("utf-8")

            # Parse JSON
            data = json.loads(json_data)

            # Extract fields
            name = data.get("ps", "VMess Server")  # ps = name/remarks
            address = data.get("add")  # add = address
            port = data.get("port")
            uuid = data.get("id")  # id = uuid
            alter_id = data.get("aid", 0)  # aid = alterID

            if not address:
                raise ValueError("Address not found in VMess config")
            if not port:
                raise ValueError("Port not found in VMess config")
            if not uuid:
                raise ValueError("UUID not found in VMess config")

            # Convert port to int if string
            if isinstance(port, str):
                port = int(port)

            # Network type
            network = data.get(
                "net", "tcp"
            )  # net = network (tcp, ws, http, grpc, etc.)

            # TLS
            tls = data.get("tls", "")  # tls = tls or xtls or empty
            security = "tls" if tls in ["tls", "xtls"] else "none"

            # SNI
            sni = data.get("sni") or data.get("host")

            # Transport settings
            path = data.get("path", "")
            host = data.get("host", "")

            # Build headers
            headers = None
            if host:
                headers = {"Host": host}

            # ALPN
            alpn = data.get("alpn")

            # Create ServerConfig
            server = ServerConfig(
                name=name,
                protocol="vmess",
                address=address,
                port=port,
                uuid=uuid,
                alter_id=alter_id,
                network=network,
                security=security,
                sni=sni,
                alpn=alpn,
                path=path if path else None,
                host=host if host else None,
                headers=headers,
            )

            return server

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse VMess JSON: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse VMess link: {e}")


def parse_vmess(link: str) -> ServerConfig:
    """Convenience function to parse VMess link.

    Args:
        link: VMess link

    Returns:
        ServerConfig object
    """
    parser = VMessParser()
    return parser.parse(link)
