#!/usr/bin/env python3
"""Auto-updater daemon for xray-client subscriptions."""

import time
import sys
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional
import threading

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.core.config import ConfigManager
from src.core.subscription import SubscriptionManager
from src.core.process_manager import ProcessManager


class SubscriptionUpdater:
    """Updates subscriptions based on config settings."""

    def __init__(self):
        """Initialize updater."""
        self.running = True  # Start with True
        self.shutdown_requested = False
        self.config_mgr = ConfigManager()
        self.sub_mgr = SubscriptionManager()
        self.process_mgr = ProcessManager()
        self.check_interval = 10  # Check config every 60 seconds
        self.main_thread = threading.current_thread()
        
        # Configure logging
        self._setup_logging()
        
        logger.info("XRAY Client subscription updater initialized")

    def _setup_logging(self):
        """Setup loguru logging configuration."""
        logger.remove()
        
        # Console handler
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
            level="DEBUG",
            colorize=True
        )
        
        # File handler with rotation
        log_dir = Path.home() / ".xray-client" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_dir / "updater_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            level="DEBUG",
            rotation="1 day",
            retention="30 days",
            compression="gz"
        )

    def start(self):
        """Start the update loop."""
        logger.info("XRAY Client subscription updater started")
        logger.info("Press Ctrl+C to stop")
        
        last_config_check = 0
        config = None
        update_interval = None
        last_update_time = {}
        
        try:
            while self.running:
                try:
                    # Check config periodically
                    if time.time() - last_config_check > self.check_interval:
                        config = self.config_mgr.load()
                        last_config_check = time.time()
                        
                        # Check if auto-update is enabled
                        if not config.settings.auto_update_subscriptions:
                            logger.debug("Auto-update is disabled in config")
                            time.sleep(self.check_interval)
                            continue
                        
                        # Get update interval from config (convert hours to seconds)
                        update_interval = config.settings.update_interval_hours * 3600
                        logger.debug(f"Update interval from config: {update_interval}s ({config.settings.update_interval_hours} hours)")
                    
                    if not config or not config.subscriptions:
                        logger.debug("No subscriptions configured")
                        time.sleep(self.check_interval)
                        continue
                    
                    now = datetime.utcnow()
                    
                    # Check each subscription
                    for sub in config.subscriptions:
                        if not self.running:
                            break
                            
                        if not sub.enabled:
                            continue
                        
                        # Check if it's time to update this subscription
                        should_update = False
                        
                        if sub.name not in last_update_time:
                            should_update = True
                            logger.info(f"First update for {sub.name}")
                        else:
                            seconds_since = (now - last_update_time[sub.name]).total_seconds()
                            if seconds_since >= update_interval:
                                should_update = True
                                logger.info(f"Scheduled update for {sub.name} ({seconds_since:.0f}s since last update)")
                        
                        if should_update:
                            self._update_subscription(sub, config)
                            last_update_time[sub.name] = now
                    

                    time.sleep(60)
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    time.sleep(5)
                    
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()
        
        logger.info("Updater stopped")

    def _update_subscription(self, sub, config):
        """Update a single subscription."""
        try:
            headers = None
            if config.settings.subscription_headers_enable:
                headers = config.settings.subscription_headers
            
            logger.info(f"Updating {sub.name}")
            logger.debug(f"URL: {sub.url[:100]}...")
            
            servers = self.sub_mgr.update_subscription(sub.url, headers=headers)
            
            self.config_mgr.update_subscription_servers(sub.name, servers)
            
            logger.success(f"Received {len(servers)} servers from {sub.name}")
            
            logger.debug(f"Servers: {servers}")  

            self._check_restart_needed(sub.name, config)
            
        except Exception as e:
            logger.error(f"Failed to update {sub.name}: {e}")

    def _check_restart_needed(self, subscription_name: str, config):
        """Check if xray needs restart after update."""
        if not self.process_mgr.is_running():
            return
        
        current = self.config_mgr.get_current_server()
        if not current or not current.subscription:
            return
        
        if current.subscription == subscription_name:
            logger.warning(f"Active subscription '{subscription_name}' was updated")
            logger.info("Restarting xray-core...")
            
            xray_binary = Path.home() / ".xray-client" / "bin" / "xray"
            
            try:
                self.process_mgr.restart(xray_binary, config)
                logger.success("Xray-core restarted successfully")
            except Exception as e:
                logger.error(f"Failed to restart xray-core: {e}")

    def stop(self):
        """Stop the updater."""
        if not self.shutdown_requested:
            logger.info("Stopping updater...")
        self.running = False
        self.shutdown_requested = True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Xray-Client Subscription Updater")
    parser.add_argument(
        "--once", 
        action="store_true",
        help="Run once and exit (don't loop)"
    )
    parser.add_argument(
        "--force", 
        action="store_true",
        help="Force update all subscriptions now"
    )
    
    args = parser.parse_args()
    
    updater = SubscriptionUpdater()
    
    if args.force:
        # Force update all subscriptions
        logger.info("Force updating all subscriptions...")
        config = updater.config_mgr.load()
        
        if not config.subscriptions:
            logger.warning("No subscriptions configured")
            return
        
        for sub in config.subscriptions:
            if sub.enabled:
                updater._update_subscription(sub, config)
        
        logger.success("Force update completed")
        return
        
    if args.once:
        # Run once and exit
        logger.info("Running one-time update check...")
        config = updater.config_mgr.load()
        
        if not config.settings.auto_update_subscriptions:
            logger.warning("Auto-update is disabled in config")
            return
        
        now = datetime.utcnow()
        
        for sub in config.subscriptions:
            if not sub.enabled:
                continue
            
            if not sub.last_update:
                updater._update_subscription(sub, config)
            else:
                last = datetime.fromisoformat(sub.last_update)
                hours_since = (now - last).total_seconds() / 3600
                
                if hours_since >= config.settings.update_interval_hours:
                    updater._update_subscription(sub, config)
                else:
                    logger.info(f"{sub.name} was updated {hours_since:.1f}h ago, skipping")
        
        logger.info("Done")
        return
    
    # Start daemon
    try:
        updater.start()
    except KeyboardInterrupt:
        updater.stop()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()