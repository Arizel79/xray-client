#!/usr/bin/env python3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.core.config import ConfigManager
from src.core.process_manager import ProcessManager
from src.core.subscription import SubscriptionManager

from src.services.xray_service import XrayService

class SubscriptionUpdater:
    def __init__(self, check_config_interval=60, polling_interval=20):
        self.running = True
        self.shutdown_requested = False
        self.config_mgr = ConfigManager()
        self.sub_mgr = SubscriptionManager()
        self.process_mgr = ProcessManager()
        self.check_config_interval = check_config_interval
        self.polling_interval = polling_interval

        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
            level="DEBUG",
            colorize=True,
        )

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
                    if time.time() - last_config_check > self.check_config_interval:
                        config = self.config_mgr.load()
                        last_config_check = time.time()
                        if not config.settings.auto_update_subscriptions:
                            logger.debug("Auto-update is disabled in config")
                            time.sleep(self.check_config_interval)
                            continue
                        update_interval = config.settings.update_interval_seconds
                        logger.debug(f"Update interval from config: {update_interval}s")

                    if not config or not config.subscriptions:
                        logger.debug("No subscriptions configured")
                        time.sleep(self.check_config_interval)
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
                            seconds_since = (
                                now - last_update_time[sub.name]
                            ).total_seconds()
                            if seconds_since >= update_interval:
                                should_update = True
                                logger.info(
                                    f"Scheduled update for {sub.name} ({seconds_since:.0f}s since last update)"
                                )
                        if should_update:
                            self._update_subscription(sub, config)
                            last_update_time[sub.name] = now

                    time.sleep(self.polling_interval)

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
            headers = (
                config.settings.subscription_headers
                if config.settings.subscription_headers_enable
                else None
            )
            logger.info(f"Updating {sub.name}")
            logger.debug(f"URL: {sub.url}.")

            # Получаем старый список серверов этой подписки
            old_servers = self.config_mgr.get_servers_by_subscription(sub.name)
            old_set = {(s.address, s.port, s.name, s.uuid) for s in old_servers}

            # Получаем новые серверы
            new_servers = self.sub_mgr.update_subscription(sub.url, headers=headers)
            new_set = {(s.address, s.port, s.name, s.uuid) for s in new_servers}

            # Обновляем конфиг (всегда, даже если без изменений, чтобы обновить last_update)
            self.config_mgr.update_subscription_servers(sub.name, new_servers)

            logger.debug(f"old: {old_set} new: {new_set}")
            if old_set == new_set:
                logger.info(f"No changes in subscription {sub.name}, restart skipped")
                return

            # Есть изменения
            added = new_set - old_set
            removed = old_set - new_set
            if added:
                logger.info(f"Added servers: {[addr[2] for addr in added]}")
            if removed:
                logger.info(f"Removed servers: {[addr[2] for addr in removed]}")

            if config.settings.restart_xray_on_autoupdate:
                self._restart_instances_for_subscription(sub.name, config)
            else:
                logger.info(
                    "Restart on autoupdate is disabled, running instances not restarted"
                )

        except Exception as e:
            logger.error(f"Failed to update {sub.name}: {e}")

    def _restart_instances_for_subscription(self, subscription_name: str, config):
        service = XrayService()
        count = service.restart_servers_by_subscription(subscription_name)
        if count > 0:
            logger.info(f"Restarted {count} server(s) for subscription {subscription_name}")
        def stop(self):
            if not self.shutdown_requested:
                logger.info("Stopping updater...")
            self.running = False
            self.shutdown_requested = True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Xray-Client Subscription Updater")
    parser.add_argument(
        "--once", action="store_true", help="Run once and exit (don't loop)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force update all subscriptions now"
    )

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
                    logger.info(
                        f"{sub.name} was updated {hours_since:.1f}h ago, skipping"
                    )
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
