"""Binary manager for downloading and managing xray-core binary."""

import hashlib
import platform
import tarfile
import zipfile
from pathlib import Path
from typing import Tuple

import httpx

from loguru import logger

class BinaryManager:
    """Manages xray-core binary download and installation."""

    GITHUB_API = "https://api.github.com/repos/XTLS/Xray-core/releases/latest"

    def __init__(self, base_dir: Path | None = None):
        """Initialize binary manager.

        Args:
            base_dir: Base directory for xray-client (default: ~/.xray-client)
        """
        self.base_dir = base_dir or Path.home() / ".xray-client"
        self.bin_dir = self.base_dir / "bin"
        self.bin_path = self.bin_dir / "xray"

    def get_platform_info(self) -> Tuple[str, str]:
        """Detect current platform and architecture.

        Returns:
            Tuple of (os_name, architecture) for xray-core download
        """
        system = platform.system().lower()
        machine = platform.machine().lower()

        # Map system names
        os_map = {"linux": "linux", "darwin": "macos", "windows": "windows"}
        os_name = os_map.get(system, system)

        # Map architectures
        arch_map = {
            "x86_64": "64",
            "amd64": "64",
            "aarch64": "arm64-v8a",
            "arm64": "arm64-v8a",
            "armv7l": "arm32-v7a",
        }
        arch = arch_map.get(machine, "64")

        logger.info(f"Detected OS: {os_name}, arch: {arch}")

        return os_name, arch

    def get_download_url(self) -> Tuple[str, str]:
        """Get download URL for current platform from GitHub releases.

        Returns:
            Tuple of (download_url, version)

        Raises:
            RuntimeError: If unable to fetch release info or find matching asset
        """
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(self.GITHUB_API)
                response.raise_for_status()
                release_data = response.json()

            version = release_data["tag_name"]
            assets = release_data["assets"]

            os_name, arch = self.get_platform_info()

            # Build expected filename pattern
            # Example: Xray-linux-64.zip, Xray-macos-arm64-v8a.zip
            if os_name == "windows":
                extension = ".zip"
            else:
                extension = ".zip"

            pattern = f"Xray-{os_name}-{arch}{extension}"

            # Find matching asset
            for asset in assets:
                if asset["name"] == pattern:
                    return asset["browser_download_url"], version

            raise RuntimeError(
                f"No matching release found for {os_name}-{arch}. "
                f"Looking for pattern: {pattern}"
            )

        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to fetch release info: {e}")

    def download_binary(self, force: bool = False) -> Path:
        """Download xray-core binary if not present.

        Args:
            force: Force re-download even if binary exists

        Returns:
            Path to xray binary

        Raises:
            RuntimeError: If download or extraction fails
        """
        # Check if binary already exists
        if self.bin_path.exists() and not force:
            return self.bin_path

        # Create directories
        self.bin_dir.mkdir(parents=True, exist_ok=True)

        # Get download URL
        download_url, version = self.get_download_url()

        logger.info(f"Downloading xray-core from {download_url!r}...")

        # Download archive
        archive_path = self.bin_dir / "xray-temp.zip"
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                with client.stream("GET", download_url) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length", 0))

                    with open(archive_path, "wb") as f:
                        downloaded = 0
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                percent = (downloaded / total) * 100
                                if percent % 10 == 0:
                                    logger.debug(f"Progress {percent:.1f}%", end="", flush=True)

        except httpx.HTTPError as e:
            raise RuntimeError(f"Download failed: {e}")

        # Extract archive
        logger.info("Extracting...")
        try:
            if archive_path.suffix == ".zip":
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    # Extract only the xray binary
                    for member in zip_ref.namelist():
                        if member.endswith("xray") or member.endswith("xray.exe"):
                            zip_ref.extract(member, self.bin_dir)
                            extracted_path = self.bin_dir / member
                            extracted_path.rename(self.bin_path)
                            break
            else:
                with tarfile.open(archive_path, "r:gz") as tar_ref:
                    for member in tar_ref.getmembers():
                        if member.name.endswith("xray") or member.name.endswith(
                            "xray.exe"
                        ):
                            tar_ref.extract(member, self.bin_dir)
                            extracted_path = self.bin_dir / member.name
                            extracted_path.rename(self.bin_path)
                            break

        except Exception as e:
            raise RuntimeError(f"Extraction failed: {e}")
        finally:
            # Clean up archive
            archive_path.unlink(missing_ok=True)

        # Make binary executable (Unix-like systems)
        if platform.system() != "Windows":
            self.bin_path.chmod(0o755)

        logger.info(f"xray-core {version} installed successfully at {self.bin_path}")
        return self.bin_path

    def ensure_binary(self) -> Path:
        """Ensure xray binary is available, download if necessary.

        Returns:
            Path to xray binary
        """
        return self.download_binary(force=False)

    def get_version(self) -> str | None:
        """Get version of installed xray binary.

        Returns:
            Version string or None if binary not found
        """
        logger.info(f"detecting xray ninary version...")
        if not self.bin_path.exists():
            return None

        import subprocess

        try:
            result = subprocess.run(
                [str(self.bin_path), "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Parse version from output (format: "Xray 1.8.8 ...")
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if lines:
                    parts = lines[0].split()
                    if len(parts) >= 2:
                        version = parts[1]
                        logger.info(f"xray binary version: {version}")
                        return version
        except Exception:
            pass

        return None
