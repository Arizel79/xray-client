"""Generate xray-core JSON configuration from ServerConfig."""

from typing import Any, Dict, Optional

from loguru import logger

from src.core.config import ServerConfig, Settings


class ConfigGenerator:
    """Generate xray-core configuration files."""

    def __init__(self, settings: Settings | None = None):
        """Initialize config generator.

        Args:
            settings: Application settings
        """
        self.settings = settings or Settings()
        logger.debug(f"ConfigGenerator initialized with log level: {self.settings.log_level}")

    def generate(self, server: ServerConfig) -> Dict[str, Any]:
        """Generate complete xray-core config for a server.

        Args:
            server: Server configuration

        Returns:
            Dictionary with xray-core config
        """
        logger.info(f"Generating xray-core config for server: {server.name} ({server.address}:{server.port})")
        logger.debug(f"Server protocol: {server.protocol}, network: {server.network}, security: {server.security}")

        config = {
            "log": {"loglevel": self.settings.log_level},
            "inbounds": self._generate_inbounds(),
            "outbounds": [self._generate_outbound(server)],
        }

        logger.success("Configuration generated successfully")
        logger.trace(f"Full config: {config}")  # Only shown at TRACE level
        return config

    def _generate_inbounds(self) -> list:
        """Generate inbound configurations (SOCKS5 and HTTP).

        Returns:
            List of inbound configs
        """
        inbounds = [
            {
                "port": self.settings.listen_socks_port,
                "listen": self.settings.listen_host,
                "protocol": "socks",
                "settings": {"udp": True, "auth": "noauth"},
                "tag": "socks-in",
            },
            {
                "port": self.settings.listen_http_port,
                "listen": self.settings.listen_host,
                "protocol": "http",
                "settings": {},
                "tag": "http-in",
            },
        ]
        logger.debug(f"Generated {len(inbounds)} inbound(s): SOCKS5 on {self.settings.listen_host}:{self.settings.listen_socks_port}, HTTP on {self.settings.listen_host}:{self.settings.listen_http_port}")
        return inbounds

    def _generate_outbound(self, server: ServerConfig) -> Dict[str, Any]:
        """Generate outbound configuration for a server.

        Args:
            server: Server configuration

        Returns:
            Outbound config dict
        """
        if server.protocol == "vless":
            logger.debug(f"Generating VLESS outbound for {server.address}:{server.port}")
            return self._generate_vless_outbound(server)
        elif server.protocol == "vmess":
            logger.debug(f"Generating VMess outbound for {server.address}:{server.port}")
            return self._generate_vmess_outbound(server)
        else:
            logger.error(f"Unsupported protocol: {server.protocol}")
            raise ValueError(f"Unsupported protocol: {server.protocol}")

    def _generate_vless_outbound(self, server: ServerConfig) -> Dict[str, Any]:
        """Generate VLESS outbound config.

        Args:
            server: Server configuration

        Returns:
            VLESS outbound config
        """
        outbound = {
            "protocol": "vless",
            "settings": {
                "vnext": [
                    {
                        "address": server.address,
                        "port": server.port,
                        "users": [
                            {
                                "id": server.uuid,
                                "encryption": "none",
                            }
                        ],
                    }
                ]
            },
            "streamSettings": self._generate_stream_settings(server),
            "tag": "proxy",
        }

        # Add flow if present
        if server.flow:
            outbound["settings"]["vnext"][0]["users"][0]["flow"] = server.flow
            logger.debug(f"VLESS flow set to: {server.flow}")

        logger.trace(f"VLESS outbound config: {outbound}")
        return outbound

    def _generate_vmess_outbound(self, server: ServerConfig) -> Dict[str, Any]:
        """Generate VMess outbound config.

        Args:
            server: Server configuration

        Returns:
            VMess outbound config
        """
        outbound = {
            "protocol": "vmess",
            "settings": {
                "vnext": [
                    {
                        "address": server.address,
                        "port": server.port,
                        "users": [
                            {
                                "id": server.uuid,
                                "alterId": server.alter_id or 0,
                                "security": "auto",
                            }
                        ],
                    }
                ]
            },
            "streamSettings": self._generate_stream_settings(server),
            "tag": "proxy",
        }
        logger.trace(f"VMess outbound config: {outbound}")
        return outbound

    def _generate_stream_settings(self, server: ServerConfig) -> Dict[str, Any]:
        """Generate stream settings (transport and security).

        Args:
            server: Server configuration

        Returns:
            Stream settings dict
        """
        logger.debug(f"Building stream settings: network={server.network}, security={server.security}")

        stream_settings = {
            "network": server.network,
        }

        # Add transport settings based on network type
        if server.network == "tcp":
            stream_settings["tcpSettings"] = {}
            logger.trace("Using TCP transport")
        elif server.network == "ws":
            stream_settings["wsSettings"] = self._generate_ws_settings(server)
            logger.trace("Using WebSocket transport")
        elif server.network == "grpc":
            stream_settings["grpcSettings"] = self._generate_grpc_settings(server)
            logger.trace("Using gRPC transport")
        elif server.network == "http":
            stream_settings["httpSettings"] = self._generate_http_settings(server)
            logger.trace("Using HTTP/2 transport")
        elif server.network == "quic":
            stream_settings["quicSettings"] = {}
            logger.trace("Using QUIC transport")

        # Add security settings
        if server.security in ["tls", "xtls"]:
            stream_settings["security"] = server.security
            stream_settings["tlsSettings"] = self._generate_tls_settings(server)
            logger.debug(f"Security: {server.security} with TLS settings")
        elif server.security == "reality":
            stream_settings["security"] = "reality"
            stream_settings["realitySettings"] = self._generate_reality_settings(server)
            logger.debug("Security: REALITY")
        else:
            stream_settings["security"] = "none"
            logger.debug("Security: none")

        return stream_settings

    def _generate_ws_settings(self, server: ServerConfig) -> Dict[str, Any]:
        """Generate WebSocket settings.

        Args:
            server: Server configuration

        Returns:
            WebSocket settings
        """
        ws_settings = {}

        if server.path:
            ws_settings["path"] = server.path
            logger.trace(f"WebSocket path: {server.path}")

        if server.headers:
            ws_settings["headers"] = server.headers
            logger.trace(f"WebSocket headers: {server.headers}")

        return ws_settings

    def _generate_grpc_settings(self, server: ServerConfig) -> Dict[str, Any]:
        """Generate gRPC settings.

        Args:
            server: Server configuration

        Returns:
            gRPC settings
        """
        grpc_settings = {}

        if server.path:
            grpc_settings["serviceName"] = server.path
            logger.trace(f"gRPC serviceName: {server.path}")

        return grpc_settings

    def _generate_http_settings(self, server: ServerConfig) -> Dict[str, Any]:
        """Generate HTTP/2 settings.

        Args:
            server: Server configuration

        Returns:
            HTTP settings
        """
        http_settings = {}

        if server.host:
            http_settings["host"] = [server.host]
            logger.trace(f"HTTP host: {server.host}")

        if server.path:
            http_settings["path"] = server.path
            logger.trace(f"HTTP path: {server.path}")

        return http_settings

    def _generate_tls_settings(self, server: ServerConfig) -> Dict[str, Any]:
        """Generate TLS settings.

        Args:
            server: Server configuration

        Returns:
            TLS settings
        """
        tls_settings = {}

        if server.sni:
            tls_settings["serverName"] = server.sni
            logger.trace(f"TLS SNI: {server.sni}")

        if server.alpn:
            # ALPN can be comma-separated
            alpn_list = [a.strip() for a in server.alpn.split(",")]
            tls_settings["alpn"] = alpn_list
            logger.trace(f"TLS ALPN: {alpn_list}")

        if server.fingerprint:
            tls_settings["fingerprint"] = server.fingerprint
            logger.trace(f"TLS fingerprint: {server.fingerprint}")

        # Allow insecure connections (useful for testing)
        tls_settings["allowInsecure"] = False
        logger.trace("TLS allowInsecure: False")

        return tls_settings

    def _generate_reality_settings(self, server: ServerConfig) -> Dict[str, Any]:
        """Generate REALITY settings.

        Args:
            server: Server configuration

        Returns:
            REALITY settings
        """
        reality_settings = {}

        if server.sni:
            reality_settings["serverName"] = server.sni
            logger.trace(f"REALITY serverName: {server.sni}")

        if server.fingerprint:
            reality_settings["fingerprint"] = server.fingerprint
            logger.trace(f"REALITY fingerprint: {server.fingerprint}")

        # REALITY-specific settings
        if server.public_key:
            reality_settings["publicKey"] = server.public_key
            logger.trace(f"REALITY publicKey: {server.public_key}")

        if server.short_id:
            reality_settings["shortId"] = server.short_id
            logger.trace(f"REALITY shortId: {server.short_id}")

        if server.spider_x:
            reality_settings["spiderX"] = server.spider_x
            logger.trace(f"REALITY spiderX: {server.spider_x}")

        return reality_settings

    def generate_for_ports(
        self,
        server: ServerConfig,
        listen_host: str = "127.0.0.1",
        socks_port: Optional[int] = None,
        http_port: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate xray-core config with custom host and ports.

        Args:
            server: Server configuration
            listen_host: Host to listen on
            socks_port: SOCKS5 port (None to disable)
            http_port: HTTP port (None to disable)

        Returns:
            Dictionary with xray-core config
        """
        logger.info(f"Generating config for server {server.name} with custom listen: host={listen_host}, socks_port={socks_port}, http_port={http_port}")

        config = {
            "log": {"loglevel": self.settings.log_level},
            "inbounds": self._generate_inbounds_for_config(listen_host, socks_port, http_port),
            "outbounds": [self._generate_outbound(server)],
        }

        logger.success("Custom configuration generated successfully")
        logger.trace(f"Custom config: {config}")
        return config

    def _generate_inbounds_for_config(
        self, listen_host: str, socks_port: Optional[int], http_port: Optional[int]
    ) -> list:
        """Generate inbound configurations with custom host and optional ports."""
        inbounds = []

        # Add SOCKS5 inbound if port specified
        if socks_port is not None:
            inbounds.append(
                {
                    "port": socks_port,
                    "listen": listen_host,
                    "protocol": "socks",
                    "settings": {"udp": True, "auth": "noauth"},
                    "tag": "socks-in",
                }
            )
            logger.debug(f"Custom SOCKS5 inbound: {listen_host}:{socks_port}")

        # Add HTTP inbound if port specified
        if http_port is not None:
            inbounds.append(
                {
                    "port": http_port,
                    "listen": listen_host,
                    "protocol": "http",
                    "settings": {},
                    "tag": "http-in",
                }
            )
            logger.debug(f"Custom HTTP inbound: {listen_host}:{http_port}")

        if not inbounds:
            logger.warning("No inbound ports specified; generated config will have no inbounds!")

        return inbounds