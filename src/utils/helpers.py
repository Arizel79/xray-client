"""Helper utilities."""

from datetime import datetime, timezone


def format_uptime(seconds: int) -> str:
    """Format uptime seconds to human-readable string.

    Args:
        seconds: Uptime in seconds

    Returns:
        Formatted string (e.g., "2h 30m", "1d 5h")
    """
    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"

    hours = minutes // 60
    minutes = minutes % 60
    if hours < 24:
        return f"{hours}h {minutes}m"

    days = hours // 24
    hours = hours % 24
    return f"{days}d {hours}h"


def format_timestamp(iso_timestamp: str | None) -> str:
    """Format ISO timestamp to human-readable string.

    Args:
        iso_timestamp: ISO format timestamp

    Returns:
        Formatted string (e.g., "2025-01-13 10:30")
    """
    if not iso_timestamp:
        return "Never"

    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_timestamp


def truncate_string(text: str, max_length: int = 50) -> str:
    """Truncate string to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated string with "..." if needed
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
