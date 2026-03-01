#!/usr/bin/env python3
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.core.config import ConfigManager
from src.core.subscription import SubscriptionManager
from src.core.process_manager import ProcessManager


class SubscriptionUpdater:
    def __init__(self):
        self.running = True
        self.shutdown_requested = False
        self.config_mgr = ConfigManager()
        self.sub_mgr = SubscriptionManager()
        self.process_mgr = ProcessManager()
        self.check_interval = 10

        logger.remove()
        logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}", level="DEBUG", colorize=True)
        log_dir = Path.home() / ".xray-client" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(log_dir / "updater_{time:YYYY-MM-DD}.log", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}", level="DEBUG", rotation="1 day", retention="30 days", compression="gz")

        logger.info("XRAY Client subscription updater initialized")

    def start(self):
        logger.info("XRAY Client subscription updater started")
        logger.info("Press Ctrl+C to stop")

        last_config_check = 0
        config = None
        update_interval = None
        last_update_time = {}

        try:
            while self.running:
                try:
                    if time.time() - last_config_check > self.check_interval:
                        config = self.config_mgr.load()
                        last_config_check = time.time()
                        if not config.settings.auto_update_subscriptions:
                            logger.debug("Auto-update is disabled in config")
                            time.sleep(self.check_interval)
                            continue
                        update_interval = config.settings.update_interval_seconds
                        logger.debug(f"Update interval from config: {update_interval}s")

                    if not config or not config.subscriptions:
                        logger.debug("No subscriptions configured")
                        time.sleep(self.check_interval)
                        continue

                    now = datetime.utcnow()
                    for sub in config.subscriptions:
                        if not self.running:
                            break
                        if not sub.enabled:
                            continue
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
        try:
            headers = config.settings.subscription_headers if config.settings.subscription_headers_enable else None
            logger.info(f"Updating {sub.name}")
            logger.debug(f"URL: {sub.url[:100]}...")

            servers = self.sub_mgr.update_subscription(sub.url, headers=headers)
            self.config_mgr.update_subscription_servers(sub.name, servers)

            logger.success(f"Received {len(servers)} servers from {sub.name}")
            logger.debug(f"Servers: {[s.name for s in servers]}")

            self._restart_instances_for_subscription(sub.name, config)

        except Exception as e:
            logger.error(f"Failed to update {sub.name}: {e}")

    def _restart_instances_for_subscription(self, subscription_name: str, config):
        running_instances = self.process_mgr.list_running_instances()
        if not running_instances:
            logger.debug(f"No running instances, no restart needed for subscription {subscription_name}")
            return

        to_restart = []
        for inst in running_instances:
            server = self.config_mgr.get_server(inst['server_id'])
            if server and server.subscription == subscription_name:
                to_restart.append(inst['server_id'])

        if not to_restart:
            logger.debug(f"No running servers belong to subscription {subscription_name}")
            return

        logger.info(f"Subscription {subscription_name} updated, restarting {len(to_restart)} running server(s)")
        for server_id in to_restart:
            try:
                logger.info(f"Restarting server {server_id}")
                self.process_mgr.restart_instance(server_id)
                logger.success(f"Server {server_id} restarted successfully")
            except Exception as e:
                logger.error(f"Failed to restart server {server_id}: {e}")

    def stop(self):
        if not self.shutdown_requested:
            logger.info("Stopping updater...")
        self.running = False
        self.shutdown_requested = True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Xray-Client Subscription Updater")
    parser.add_argument("--once", action="store_true", help="Run once and exit (don't loop)")
    parser.add_argument("--force", action="store_true", help="Force update all subscriptions now")

    args = parser.parse_args()

    updater = SubscriptionUpdater()

    if args.force:
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
                if hours_since >= config.settings.update_interval_seconds / 3600:
                    updater._update_subscription(sub, config)
                else:
                    logger.info(f"{sub.name} was updated {hours_since:.1f}h ago, skipping")
        logger.info("Done")
        return

    try:
        updater.start()
    except KeyboardInterrupt:
        updater.stop()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()