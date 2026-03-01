import sys
from src.cli.cli import cli
from src.cli.shell import shell
from src.core.config import ConfigManager
from src.utils.logging import setup_logging


def main():
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
        setup_logging(config.settings)
    except Exception as e:
        # Fallback: basic logging to stderr
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        logger.error(f"Failed to load config for logging: {e}")

    if len(sys.argv) == 1:
        shell()
    else:
        cli()

if __name__ == "__main__":
    main()