"""Latency testing utilities for servers."""

import asyncio
import socket
import time
from typing import Dict, List, Optional

from src.core.config import ServerConfig


async def test_tcp_latency(
    host: str, port: int, timeout: float = 5.0
) -> Optional[float]:
    """Test TCP connection latency to a server.

    Args:
        host: Server hostname or IP
        port: Server port
        timeout: Connection timeout in seconds

    Returns:
        Latency in milliseconds or None if failed
    """
    try:
        start_time = time.time()

        # Create connection with timeout
        conn = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Close connection
        writer.close()
        await writer.wait_closed()

        return round(latency_ms, 2)

    except asyncio.TimeoutError:
        return None
    except (socket.gaierror, ConnectionRefusedError, OSError):
        return None
    except Exception:
        return None


async def test_server_latency(
    server: ServerConfig, timeout: float = 5.0
) -> Dict[str, any]:
    """Test latency for a server.

    Args:
        server: Server configuration
        timeout: Connection timeout in seconds

    Returns:
        Dictionary with test results
    """
    latency = await test_tcp_latency(server.address, server.port, timeout)

    return {
        "server_id": server.id,
        "server_name": server.name,
        "address": server.address,
        "port": server.port,
        "latency_ms": latency,
        "status": "ok" if latency is not None else "timeout",
    }


async def test_multiple_servers(
    servers: List[ServerConfig], timeout: float = 5.0
) -> List[Dict[str, any]]:
    """Test latency for multiple servers concurrently.

    Args:
        servers: List of server configurations
        timeout: Connection timeout in seconds

    Returns:
        List of test results
    """
    tasks = [test_server_latency(server, timeout) for server in servers]
    results = await asyncio.gather(*tasks)
    return results


def test_server_sync(server: ServerConfig, timeout: float = 5.0) -> Dict[str, any]:
    """Synchronous wrapper for testing a single server.

    Args:
        server: Server configuration
        timeout: Connection timeout in seconds

    Returns:
        Dictionary with test results
    """
    return asyncio.run(test_server_latency(server, timeout))


def test_multiple_servers_sync(
    servers: List[ServerConfig], timeout: float = 5.0
) -> List[Dict[str, any]]:
    """Synchronous wrapper for testing multiple servers.

    Args:
        servers: List of server configurations
        timeout: Connection timeout in seconds

    Returns:
        List of test results
    """
    return asyncio.run(test_multiple_servers(servers, timeout))
