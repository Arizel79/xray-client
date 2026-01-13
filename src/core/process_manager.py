"""Process management for xray-core subprocess."""

import json
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

import psutil


class ProcessManager:
    """Manages xray-core process lifecycle."""

    def __init__(self, base_dir: Path | None = None):
        """Initialize process manager.

        Args:
            base_dir: Base directory for xray-client (default: ~/.xray-client)
        """
        self.base_dir = base_dir or Path.home() / ".xray-client"
        self.pid_file = self.base_dir / "xray.pid"
        self.config_file = self.base_dir / "running_config.json"
        self.log_dir = self.base_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def is_running(self) -> bool:
        """Check if xray process is running.

        Returns:
            True if process is running
        """
        pid = self.get_pid()
        if pid is None:
            return False

        try:
            process = psutil.Process(pid)
            # Check if it's actually xray
            if "xray" in process.name().lower():
                return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return False

    def get_pid(self) -> Optional[int]:
        """Get PID of running xray process.

        Returns:
            PID or None if not running
        """
        if not self.pid_file.exists():
            return None

        try:
            with open(self.pid_file, "r") as f:
                pid = int(f.read().strip())
            return pid
        except (ValueError, IOError):
            return None

    def start(self, xray_binary: Path, config: dict) -> None:
        """Start xray-core process.

        Args:
            xray_binary: Path to xray binary
            config: Xray configuration dict

        Raises:
            RuntimeError: If start fails or already running
        """
        if self.is_running():
            raise RuntimeError("Xray is already running")

        # Write config to file
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        # Start xray process
        log_file = self.log_dir / "xray.log"
        error_log_file = self.log_dir / "xray_error.log"

        try:
            with open(log_file, "a") as out, open(error_log_file, "a") as err:
                process = subprocess.Popen(
                    [str(xray_binary), "run", "-c", str(self.config_file)],
                    stdout=out,
                    stderr=err,
                    start_new_session=True,  # Detach from parent process
                )

            # Write PID file
            with open(self.pid_file, "w") as f:
                f.write(str(process.pid))

            # Wait a bit and check if process started successfully
            time.sleep(0.5)

            if not self.is_running():
                # Process died immediately, read error log
                with open(error_log_file, "r") as f:
                    error = f.read()[-500:]  # Last 500 chars
                raise RuntimeError(f"Xray failed to start. Error: {error}")

        except Exception as e:
            # Clean up PID file if exists
            self.pid_file.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to start xray: {e}")

    def stop(self, timeout: int = 5) -> bool:
        """Stop xray-core process.

        Args:
            timeout: Seconds to wait for graceful shutdown

        Returns:
            True if stopped successfully
        """
        pid = self.get_pid()
        if pid is None:
            return False

        try:
            process = psutil.Process(pid)

            # Send SIGTERM for graceful shutdown
            process.terminate()

            # Wait for process to exit
            try:
                process.wait(timeout=timeout)
            except psutil.TimeoutExpired:
                # Force kill if graceful shutdown failed
                process.kill()
                process.wait(timeout=2)

            return True

        except psutil.NoSuchProcess:
            return False

        finally:
            # Clean up PID file
            self.pid_file.unlink(missing_ok=True)

    def get_status(self) -> dict:
        """Get status information about xray process.

        Returns:
            Dictionary with status info
        """
        if not self.is_running():
            return {
                "running": False,
                "pid": None,
                "uptime": None,
                "memory_mb": None,
                "cpu_percent": None,
            }

        pid = self.get_pid()
        try:
            process = psutil.Process(pid)

            # Get process info
            create_time = process.create_time()
            uptime_seconds = int(time.time() - create_time)

            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB

            cpu_percent = process.cpu_percent(interval=0.1)

            return {
                "running": True,
                "pid": pid,
                "uptime": uptime_seconds,
                "memory_mb": round(memory_mb, 2),
                "cpu_percent": round(cpu_percent, 2),
            }

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {
                "running": False,
                "pid": None,
                "uptime": None,
                "memory_mb": None,
                "cpu_percent": None,
            }

    def get_logs(self, lines: int = 50, error: bool = False) -> str:
        """Get recent log lines.

        Args:
            lines: Number of lines to retrieve
            error: If True, get error log instead of stdout

        Returns:
            Log content
        """
        log_file = self.log_dir / ("xray_error.log" if error else "xray.log")

        if not log_file.exists():
            return ""

        try:
            with open(log_file, "r") as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except IOError:
            return ""

    def restart(self, xray_binary: Path, config: dict) -> None:
        """Restart xray-core process.

        Args:
            xray_binary: Path to xray binary
            config: Xray configuration dict
        """
        if self.is_running():
            self.stop()

        # Wait a bit before restart
        time.sleep(0.5)

        self.start(xray_binary, config)
