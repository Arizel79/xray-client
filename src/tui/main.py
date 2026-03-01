# src/tui/main.py
"""Textual TUI for xray-client."""

import asyncio
from typing import List, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, DataTable, Button, Label, Input,
    TabbedContent, TabPane, RichLog, Static
)
from textual import work
from textual.reactive import reactive
from textual.message import Message
from textual.worker import Worker, WorkerState

from src.core.config import ConfigManager, ServerConfig, Subscription, Settings
from src.core.process_manager import ProcessManager
from src.core.subscription import SubscriptionManager
from src.core.binary_manager import BinaryManager
from src.core.config_generator import ConfigGenerator
from src.parsers.base import BaseParser
from src.parsers.vless import VLESSParser
from src.parsers.vmess import VMessParser


class ServerTable(DataTable):
    """Table displaying servers with live status."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_columns("ID", "Name", "Protocol", "Address", "Status")
        self.cursor_type = "row"

    def update_servers(self, servers: List[ServerConfig], statuses: dict):
        """Refresh table with server list and statuses."""
        self.clear()
        if not servers:
            self.add_row("", "No servers found", "", "", "")
            return
        for server in servers:
            status = statuses.get(server.id, {}).get("running", False)
            status_text = "running" if status else "stopped"
            self.add_row(
                str(server.id),
                server.name,
                server.protocol,
                f"{server.address}:{server.port}",
                status_text
            )


class ServerDetail(Vertical):
    """Widget showing detailed server information."""

    def __init__(self, server: Optional[ServerConfig] = None, **kwargs):
        super().__init__(**kwargs)
        self.server = server

    def compose(self) -> ComposeResult:
        yield Label("Server details", classes="title")
        if self.server:
            yield Label(f"Name: {self.server.name}")
            yield Label(f"Protocol: {self.server.protocol}")
            yield Label(f"Address: {self.server.address}:{self.server.port}")
            yield Label(f"UUID: {self.server.uuid}")
            if self.server.network:
                yield Label(f"Network: {self.server.network}")
            if self.server.security:
                yield Label(f"Security: {self.server.security}")
            if self.server.sni:
                yield Label(f"SNI: {self.server.sni}")
            yield Label(f"Subscription: {self.server.subscription or 'none'}")
        else:
            yield Label("No server selected")

    def set_server(self, server: ServerConfig):
        self.server = server
        self.refresh(recompose=True)


class SubscriptionList(ScrollableContainer):
    """Widget listing subscriptions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscriptions: List[Subscription] = []

    def compose(self) -> ComposeResult:
        for sub in self.subscriptions:
            yield Button(f"{sub.name} ({sub.url[:30]}...)", id=f"sub_{sub.name}")

    def update_subscriptions(self, subs: List[Subscription]):
        self.subscriptions = subs
        self.refresh(recompose=True)


class LogViewer(RichLog):
    """Widget for displaying logs with auto-refresh."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server_id: Optional[int] = None
        self.auto_refresh = False

    async def refresh_logs(self, server_id: int, error: bool = False, lines: int = 100):
        """Load logs from process manager."""
        if not server_id:
            return
        pm = ProcessManager()
        logs = await asyncio.to_thread(pm.get_instance_logs, server_id, lines, error)
        self.clear()
        self.write(logs)


class AddServerModal(Static):
    """Modal dialog for adding a server via link."""

    def compose(self) -> ComposeResult:
        yield Label("Add server from link", classes="title")
        yield Input(placeholder="vless://... or vmess://...", id="add-link")
        with Horizontal():
            yield Button("Add", id="add-confirm", variant="primary")
            yield Button("Cancel", id="add-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-cancel":
            self.remove()
        elif event.button.id == "add-confirm":
            link = self.query_one("#add-link", Input).value
            if link:
                self.post_message(self.AddServer(link))
            self.remove()

    class AddServer(Message):
        def __init__(self, link: str):
            self.link = link
            super().__init__()


class XrayTUIApp(App):
    """Main TUI application for xray-client."""

    CSS = """
    Screen {
        background: $surface;
    }

    .title {
        text-style: bold;
        margin: 1 0;
    }

    ServerTable {
        height: 100%;
        margin: 1 0;
    }

    ServerDetail {
        border: solid $primary;
        padding: 1;
        height: auto;
        margin: 1 0;
    }

    #server-controls {
        height: 3;
        margin: 1 0;
    }

    Button {
        margin: 0 1;
    }

    #subscription-panel {
        height: 100%;
    }

    LogViewer {
        border: solid $primary;
        margin: 1 0;
        padding: 1;
    }

    AddServerModal {
        background: $surface;
        border: thick $primary;
        padding: 2;
        width: 60;
        height: 12;
        align: center middle;
    }
    """

    def __init__(self):
        super().__init__()
        self.config_mgr = ConfigManager()
        self.process_mgr = ProcessManager()
        self.sub_mgr = SubscriptionManager()
        self.servers: List[ServerConfig] = []
        self.subscriptions: List[Subscription] = []
        self.selected_server_id: Optional[int] = None
        self.statuses: dict = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with TabbedContent(initial="servers"):
            with TabPane("Servers", id="servers"):
                yield ServerTable(id="server-table")
                with Horizontal(id="server-controls"):
                    yield Button("Start", id="start", variant="success")
                    yield Button("Stop", id="stop", variant="error")
                    yield Button("Restart", id="restart", variant="warning")
                    yield Button("Logs", id="logs", variant="default")
                    yield Button("Remove", id="remove", variant="error")
                    yield Button("Add", id="add-server", variant="primary")
                    yield Button("Refresh", id="refresh", variant="primary")
                yield ServerDetail(id="server-detail")
            with TabPane("Subscriptions", id="subscriptions"):
                yield SubscriptionList(id="sub-list")
                with Horizontal():
                    yield Button("Add", id="sub-add", variant="primary")
                    yield Button("Update", id="sub-update", variant="primary")
                    yield Button("Remove", id="sub-remove", variant="error")
                with Container(id="sub-detail"):
                    yield Label("Select a subscription", id="sub-info")
            with TabPane("Settings", id="settings"):
                yield Label("Settings coming soon", classes="title")
            with TabPane("Logs", id="logs-pane"):
                yield LogViewer(id="log-viewer")
                with Horizontal():
                    yield Button("Refresh", id="log-refresh", variant="primary")
                    yield Button("Error log", id="log-error", variant="warning")

    def on_mount(self) -> None:
        """Load initial data and start periodic updates."""
        self.load_servers_and_subs()
        self.set_interval(2, self.update_statuses)  # update every 2 sec

    async def load_servers_and_subs(self):
        """Load servers and subscriptions from config (runs in thread)."""
        try:
            config = await asyncio.to_thread(self.config_mgr.load)
            self.servers = config.servers
            self.subscriptions = config.subscriptions
            self.update_server_table()
            self.update_subscription_list()
        except Exception as e:
            self.notify(f"Failed to load config: {e}", severity="error")

    def update_server_table(self):
        """Refresh server table with current statuses."""
        table = self.query_one("#server-table", ServerTable)
        table.update_servers(self.servers, self.statuses)
        self.restore_selection()

    def update_subscription_list(self):
        """Refresh subscription list."""
        sub_list = self.query_one("#sub-list", SubscriptionList)
        sub_list.update_subscriptions(self.subscriptions)

    async def update_statuses(self):
        """Fetch statuses for all servers."""
        statuses = {}
        for server in self.servers:
            try:
                status = await asyncio.to_thread(self.process_mgr.get_instance_status, server.id)
                statuses[server.id] = status
            except Exception:
                statuses[server.id] = {"running": False}
        self.statuses = statuses
        self.update_server_table()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle server selection."""
        table = event.data_table
        row_key = event.row_key
        row = table.get_row(row_key)
        if row and len(row) > 0 and row[0] != "":
            try:
                server_id = int(row[0])
                self.selected_server_id = server_id
                server = next((s for s in self.servers if s.id == server_id), None)
                if server:
                    detail = self.query_one("#server-detail", ServerDetail)
                    detail.set_server(server)
            except ValueError:
                pass

    def restore_selection(self):
        """Restore cursor to previously selected server if it still exists."""
        if self.selected_server_id is None:
            return
        table = self.query_one("#server-table", ServerTable)
        # Find row with matching ID
        for row_key, row in table.rows.items():
            cells = table.get_row(row_key)
            if cells and cells[0] == str(self.selected_server_id):
                table.move_cursor(row_key)
                # Update detail view
                server = next((s for s in self.servers if s.id == self.selected_server_id), None)
                if server:
                    detail = self.query_one("#server-detail", ServerDetail)
                    detail.set_server(server)
                break

    def get_selected_server(self) -> Optional[ServerConfig]:
        """Return currently selected server or None."""
        if self.selected_server_id is None:
            return None
        return next((s for s in self.servers if s.id == self.selected_server_id), None)

    @work
    async def start_server(self, server_id: int):
        """Start a server (background worker)."""
        server = next((s for s in self.servers if s.id == server_id), None)
        if not server:
            self.notify("Server not found", severity="error")
            return

        config = await asyncio.to_thread(self.config_mgr.load)
        settings = config.settings
        xray_path = await asyncio.to_thread(BinaryManager().ensure_binary)

        generator = ConfigGenerator(settings)
        xray_config = generator.generate_for_ports(
            server,
            listen_host=settings.listen_host,
            socks_port=settings.listen_socks_port,
            http_port=settings.listen_http_port,
        )

        try:
            instance_id = await asyncio.to_thread(
                self.process_mgr.start_instance,
                server_id,
                xray_path,
                xray_config,
                listen_host=settings.listen_host,
                socks_port=settings.listen_socks_port,
                http_port=settings.listen_http_port,
            )
            self.notify(f"Server {server.name} started", severity="information")
            # Force immediate status update
            self.call_later(self.update_statuses)
        except Exception as e:
            self.notify(f"Failed to start: {e}", severity="error")

    @work
    async def stop_server(self, server_id: int):
        """Stop a server."""
        try:
            success = await asyncio.to_thread(self.process_mgr.stop_instance, server_id)
            if success:
                self.notify("Server stopped", severity="information")
            else:
                self.notify("Server not running", severity="warning")
            self.call_later(self.update_statuses)
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    @work
    async def restart_server(self, server_id: int):
        """Restart a server."""
        try:
            success = await asyncio.to_thread(self.process_mgr.restart_instance, server_id)
            if success:
                self.notify("Server restarted", severity="information")
            else:
                self.notify("Failed to restart", severity="error")
            self.call_later(self.update_statuses)
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        button_id = event.button.id
        server = self.get_selected_server()

        if button_id == "start":
            if server:
                self.start_server(server.id)
            else:
                self.notify("No server selected", severity="warning")
        elif button_id == "stop":
            if server:
                self.stop_server(server.id)
            else:
                self.notify("No server selected", severity="warning")
        elif button_id == "restart":
            if server:
                self.restart_server(server.id)
            else:
                self.notify("No server selected", severity="warning")
        elif button_id == "remove":
            if server:
                await self.remove_server(server.id)
            else:
                self.notify("No server selected", severity="warning")
        elif button_id == "logs":
            if server:
                self.query_one(TabbedContent).active = "logs-pane"
                log_view = self.query_one("#log-viewer", LogViewer)
                log_view.server_id = server.id
                await log_view.refresh_logs(server.id, error=False)
            else:
                self.notify("No server selected", severity="warning")
        elif button_id == "refresh":
            await self.load_servers_and_subs()
        elif button_id == "add-server":
            self.mount(AddServerModal())
        elif button_id == "log-refresh":
            log_view = self.query_one("#log-viewer", LogViewer)
            if log_view.server_id:
                await log_view.refresh_logs(log_view.server_id, error=False)
        elif button_id == "log-error":
            log_view = self.query_one("#log-viewer", LogViewer)
            if log_view.server_id:
                await log_view.refresh_logs(log_view.server_id, error=True)
        # Subscription buttons
        elif button_id == "sub-add":
            self.notify("Add subscription (not implemented)", severity="warning")
        elif button_id == "sub-update":
            await self.update_subscriptions()
        elif button_id == "sub-remove":
            self.notify("Remove subscription (not implemented)", severity="warning")

    async def remove_server(self, server_id: int):
        """Remove server from config."""
        status = await asyncio.to_thread(self.process_mgr.get_instance_status, server_id)
        if status["running"]:
            self.notify("Stop server before removing", severity="error")
            return
        success = await asyncio.to_thread(self.config_mgr.remove_server, server_id)
        if success:
            self.notify("Server removed")
            await self.load_servers_and_subs()
        else:
            self.notify("Failed to remove server", severity="error")

    async def update_subscriptions(self):
        """Update all subscriptions."""
        config = await asyncio.to_thread(self.config_mgr.load)
        headers = config.settings.subscription_headers if config.settings.subscription_headers_enable else None
        for sub in config.subscriptions:
            if not sub.enabled:
                continue
            self.notify(f"Updating {sub.name}...")
            try:
                servers = await asyncio.to_thread(self.sub_mgr.update_subscription, sub.url, headers)
                await asyncio.to_thread(self.config_mgr.update_subscription_servers, sub.name, servers)
                self.notify(f"{sub.name} updated ({len(servers)} servers)")
            except Exception as e:
                self.notify(f"Failed to update {sub.name}: {e}", severity="error")
        await self.load_servers_and_subs()

    async def on_add_server_modal_add_server(self, message: AddServerModal.AddServer):
        """Handle adding a server from modal."""
        link = message.link
        try:
            protocol = BaseParser.detect_protocol(link)
            if protocol == "vless":
                parser = VLESSParser()
            elif protocol == "vmess":
                parser = VMessParser()
            else:
                self.notify(f"Unsupported protocol: {protocol}", severity="error")
                return
            server = parser.parse(link)
            await asyncio.to_thread(self.config_mgr.add_server, server)
            self.notify(f"Added server: {server.name}")
            await self.load_servers_and_subs()
        except Exception as e:
            self.notify(f"Failed to add server: {e}", severity="error")


def main():
    """Entry point for TUI."""
    app = XrayTUIApp()
    app.run()


if __name__ == "__main__":
    main()