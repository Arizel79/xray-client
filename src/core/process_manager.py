"""Process management for multiple xray-core subprocesses."""

import json
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import psutil

from src.core.config import ConfigManager, RunningInstance


class ProcessManager:
    """Manages multiple xray-core process instances."""

    def __init__(self, base_dir: Path | None = None):
        """Initialize process manager.

        Args:
            base_dir: Base directory for xray-client (default: ~/.xray-client)
        """
        self.base_dir = base_dir or Path.home() / ".xray-client"
        self.instances_dir = self.base_dir / "instances"
        self.instances_dir.mkdir(parents=True, exist_ok=True)
        self.instances_file = self.base_dir / "running_instances.json"
        self.log_dir = self.base_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _save_instances(self, instances: Dict[str, RunningInstance]) -> None:
        """Save running instances information."""
        data = {inst_id: inst.model_dump() for inst_id, inst in instances.items()}
        with open(self.instances_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load_instances(self) -> Dict[str, RunningInstance]:
        """Load running instances information."""
        if not self.instances_file.exists():
            return {}

        try:
            with open(self.instances_file, "r") as f:
                data = json.load(f)

            return {
                inst_id: RunningInstance(**inst_data)
                for inst_id, inst_data in data.items()
            }
        except Exception:
            return {}

    def start_instance(
        self,
        server_id: int,
        xray_binary: Path,
        config: dict,
        listen_host: str = "127.0.0.1",
        socks_port: Optional[int] = None,
        http_port: Optional[int] = None,
    ) -> str:
        """Start a new xray instance for a specific server.

        Args:
            server_id: Server ID
            xray_binary: Path to xray binary
            config: Xray configuration dict
            listen_host: Host to listen on
            socks_port: SOCKS5 port for this instance (None to disable)
            http_port: HTTP port for this instance (None to disable)

        Returns:
            Instance ID

        Raises:
            RuntimeError: If start fails or instance already running
        """
        # Check if this server is already running
        instances = self._load_instances()
        for inst in instances.values():
            if inst.server_id == server_id and inst.status == "running":
                # Verify if process is actually running
                try:
                    process = psutil.Process(inst.pid)
                    if process.is_running():
                        raise RuntimeError(
                            f"Server {server_id} is already running (PID: {inst.pid})"
                        )
                    else:
                        # Stale record
                        inst.status = "stopped"
                except psutil.NoSuchProcess:
                    # Stale record
                    inst.status = "stopped"

        # Create instance directory
        instance_dir = self.instances_dir / str(server_id)
        instance_dir.mkdir(exist_ok=True)

        # Write config file
        config_file = instance_dir / "config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        # Log files for this instance
        log_file = instance_dir / "xray.log"
        error_log = instance_dir / "xray_error.log"

        # Start process
        try:
            with open(log_file, "a") as out, open(error_log, "a") as err:
                process = subprocess.Popen(
                    [str(xray_binary), "run", "-c", str(config_file)],
                    stdout=out,
                    stderr=err,
                    start_new_session=True,
                )

            # Wait a bit and check if process started successfully
            time.sleep(0.5)

            # Check if process is still running
            if process.poll() is not None:
                # Process died immediately, read error log
                with open(error_log, "r") as f:
                    error = f.read()[-500:]  # Last 500 chars
                raise RuntimeError(f"Xray failed to start. Error: {error}")

            # Create instance record
            instance_id = f"server_{server_id}_{process.pid}"
            instance = RunningInstance(
                instance_id=instance_id,
                server_id=server_id,
                pid=process.pid,
                start_time=datetime.utcnow().isoformat(),
                config_path=str(config_file),
                listen_host=listen_host,
                listen_socks_port=socks_port,
                listen_http_port=http_port,
                status="running",
            )

            instances[instance_id] = instance
            self._save_instances(instances)

            return instance_id

        except Exception as e:
            # Clean up if something went wrong
            if "process" in locals():
                process.kill()
            raise RuntimeError(f"Failed to start xray instance: {e}")

    def restart_instance(self, server_id: int, timeout: int = 5) -> bool:
        """Restart a running instance for a specific server.

        Returns:
            True if restarted successfully.
        """
        from src.core.binary_manager import BinaryManager
        from src.core.config_generator import ConfigGenerator

        status = self.get_instance_status(server_id)
        if not status["running"]:
            return False

        config_mgr = ConfigManager()
        server = config_mgr.get_server(server_id)
        if not server:
            raise RuntimeError(f"Server {server_id} not found in config")

        if not self.stop_instance(server_id, timeout):
            if status["pid"]:
                try:
                    proc = psutil.Process(status["pid"])
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception as e:
                    print(f"Force kill failed for PID {status['pid']}: {e}")
                    return False

        config_gen = ConfigGenerator(config_mgr.load().settings)
        xray_config = config_gen.generate_for_ports(
            server,
            listen_host=status["listen_host"],
            socks_port=status["socks_port"],
            http_port=status["http_port"],
        )

        binary_mgr = BinaryManager()
        xray_path = binary_mgr.ensure_binary()
        try:
            self.start_instance(
                server_id,
                xray_path,
                xray_config,
                listen_host=status["listen_host"],
                socks_port=status["socks_port"],
                http_port=status["http_port"],
            )
            return True
        except RuntimeError as e:
            print(f"Failed to start new instance after restart: {e}")
            return False

    def stop_instance(self, server_id: int, timeout: int = 5) -> bool:
        """Stop xray instance for a specific server.

        Returns:
            True if at least one instance was successfully stopped (or marked as stopped).
        """
        instances = self._load_instances()
        stopped = False

        to_stop = [
            (inst_id, inst)
            for inst_id, inst in instances.items()
            if inst.server_id == server_id and inst.status == "running"
        ]

        for inst_id, inst in to_stop:
            try:
                process = psutil.Process(inst.pid)
                process.terminate()
                try:
                    process.wait(timeout=timeout)
                except psutil.TimeoutExpired:
                    process.kill()
                    # После kill ждём немного, но если не умер – продолжаем, процесс будет помечен как stopped
                    try:
                        process.wait(timeout=2)
                    except psutil.TimeoutExpired:
                        # Даже если не умер, считаем, что запись недействительна
                        pass
                inst.status = "stopped"
                stopped = True
            except psutil.NoSuchProcess:
                inst.status = "stopped"
                stopped = True
            except Exception as e:
                print(f"Error stopping instance {inst_id}: {e}")
                # В любом случае помечаем как остановленный, чтобы избежать конфликтов
                inst.status = "stopped"
                stopped = True

        self._save_instances(instances)
        return stopped

    def stop_all(self, timeout: int = 5) -> int:
        """Stop all running xray instances.

        Args:
            timeout: Seconds to wait for graceful shutdown

        Returns:
            Number of instances stopped
        """
        instances = self._load_instances()
        stopped_count = 0

        for inst_id, inst in list(instances.items()):
            if inst.status != "running":
                continue

            try:
                process = psutil.Process(inst.pid)
                process.terminate()

                try:
                    process.wait(timeout=timeout)
                except psutil.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)

                inst.status = "stopped"
                stopped_count += 1

            except psutil.NoSuchProcess:
                inst.status = "stopped"
                stopped_count += 1
            except Exception:
                continue

        self._save_instances(instances)
        return stopped_count

    def get_instance_status(self, server_id: int) -> dict:
        """Get status of instance for a specific server.

        Args:
            server_id: Server ID

        Returns:
            Dictionary with status info
        """
        instances = self._load_instances()

        for inst in instances.values():
            if inst.server_id == server_id and inst.status == "running":
                try:
                    process = psutil.Process(inst.pid)

                    # Get process info
                    create_time = process.create_time()
                    uptime_seconds = int(time.time() - create_time)

                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / (1024 * 1024)

                    cpu_percent = process.cpu_percent(interval=0.1)

                    # Формируем информацию о прокси
                    proxies = []
                    if inst.listen_socks_port:
                        proxies.append(
                            f"SOCKS5: {inst.listen_host}:{inst.listen_socks_port}"
                        )
                    if inst.listen_http_port:
                        proxies.append(
                            f"HTTP: {inst.listen_host}:{inst.listen_http_port}"
                        )

                    return {
                        "running": True,
                        "pid": inst.pid,
                        "uptime": uptime_seconds,
                        "memory_mb": round(memory_mb, 2),
                        "cpu_percent": round(cpu_percent, 2),
                        "listen_host": inst.listen_host,
                        "socks_port": inst.listen_socks_port,
                        "http_port": inst.listen_http_port,
                        "proxies": (
                            ", ".join(proxies) if proxies else "No proxies enabled"
                        ),
                        "instance_id": inst.instance_id,
                    }

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process is dead, update status
                    inst.status = "stopped"
                    self._save_instances(instances)
                    break

        return {
            "running": False,
            "pid": None,
            "uptime": None,
            "memory_mb": None,
            "cpu_percent": None,
            "listen_host": None,
            "socks_port": None,
            "http_port": None,
            "proxies": None,
            "instance_id": None,
        }

    def list_running_instances(self) -> List[dict]:
        """List all running instances.

        Returns:
            List of dictionaries with instance info
        """
        instances = self._load_instances()
        result = []

        for inst_id, inst in list(instances.items()):
            if inst.status != "running":
                continue

            try:
                process = psutil.Process(inst.pid)

                result.append(
                    {
                        "instance_id": inst_id,
                        "server_id": inst.server_id,
                        "pid": inst.pid,
                        "uptime": int(time.time() - process.create_time()),
                        "listen_host": inst.listen_host,
                        "socks_port": inst.listen_socks_port,
                        "http_port": inst.listen_http_port,
                        "status": "running",
                    }
                )
            except psutil.NoSuchProcess:
                # Stale record
                inst.status = "stopped"
                self._save_instances(instances)
            except Exception:
                continue

        return result

    def get_instance_logs(
        self, server_id: int, lines: int = 50, error: bool = False
    ) -> str:
        """Get logs for a specific instance.

        Args:
            server_id: Server ID
            lines: Number of lines
            error: If True, get error log

        Returns:
            Log content
        """
        log_file = (
            self.instances_dir
            / str(server_id)
            / ("xray_error.log" if error else "xray.log")
        )

        if not log_file.exists():
            return ""

        try:
            with open(log_file, "r") as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except IOError:
            return ""
 