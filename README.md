# XRAY Client

Python CLI client for XRAY/VLESS VPN with subscription support. A lightweight, easy-to-use alternative to GUI clients with full support for subscriptions from c, v2raytun, and other standard providers.

## Features

- **Protocol Support**: VLESS and VMess with full transport options (TCP, WebSocket, gRPC, HTTP/2, QUIC)
- **Security**: TLS, XTLS, and REALITY support
- **Subscription Management**: Automatic server updates from subscription URLs
- **Automatic Setup**: Downloads and manages xray-core binary automatically
- **Server Testing**: Built-in latency testing to find fastest servers
- **Background Operation**: Runs as daemon process, survives terminal closure
- **Process Monitoring**: Real-time CPU, memory, and uptime statistics

## Installation

### Prerequisites

- Python 3.13+
- Linux, macOS, or Windows
- uv package manager (recommended) or pip

### Install

```bash
# Clone the repository
git clone <repository-url>
cd xray-client

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

## Quick Start

### 1. Add Your Subscription

```bash
# Add subscription from your provider (Marzban, v2raytun, etc.)
uv run xray-client subscribe add "my-vpn" "http://your-subscription-url"

# Fetch servers from subscription
uv run xray-client subscribe update
```

## HWID (Hardware ID) Support
Some subscription services require HWID (Hardware ID) authentication. XRAY Client supports sending custom HWID headers with subscription requests.

```bash
# Enable HWID support
uv run xray-client hwid enable

# Disable HWID support
uv run xray-client hwid disable

# Set HWID string
uv run xray-client hwid set "your-hwid-value"

# Set random HWID string
uv run xray-client hwid set "${uidgen}"

# Check HWID status
uv run xray-client hwid status
```

### 2. Test and Connect

```bash
# List available servers
uv run xray-client list

# Test server latency (optional)
uv run xray-client test

# Connect to a server
uv run xray-client connect "server-name"

# Check connection status
uv run xray-client status
```

### 3. Configure Your Applications

Once connected, configure your applications to use the local proxy:
- **SOCKS5**: `127.0.0.1:1080`
- **HTTP**: `127.0.0.1:1081`

### 4. Disconnect When Done

```bash
uv run xray-client disconnect
```

## Usage Guide

### Server Management

```bash
# Add a server from share link
uv run xray-client add "vless://uuid@host:port?params#name"
uv run xray-client add "vmess://base64-encoded-config"

# Add with custom name
uv run xray-client add "vless://..." --name "My Server"

# List all servers
uv run xray-client list

# Sort by protocol or subscription
uv run xray-client list --sort-by protocol

# Remove a server
uv run xray-client remove "server-id"
```

### Subscription Management

```bash
# Add subscription
uv run xray-client subscribe add "subscription-name" "https://subscription-url"

# Update all subscriptions
uv run xray-client subscribe update

# Update specific subscription
uv run xray-client subscribe update "subscription-name"

# List subscriptions
uv run xray-client subscribe list

# Remove subscription (keeps servers by default)
uv run xray-client subscribe remove "subscription-name"

# Remove subscription and its servers
uv run xray-client subscribe remove "subscription-name"
```

### Connection Management

```bash
# Connect to server (by name or ID)
uv run xray-client connect "server-name"
uv run xray-client connect "server-id"

# Check connection status
uv run xray-client status

# Disconnect
uv run xray-client disconnect
```

### Server Testing

```bash
# Test all servers
uv run xray-client test

# Test specific server
uv run xray-client test "server-id"

# Custom timeout (default: 5 seconds)
uv run xray-client test --timeout 10
```

## System-Wide Proxy Setup

By default, xray-client runs as a local proxy that you configure per-application. For system-wide proxy (like TUN mode in Windows), you have several options:

### Option 1: with-proxy Function (Recommended - Easiest)

The easiest way to run any command through the proxy is using the `with-proxy` shell function.

**Installation** (already added to your ~/.zshrc during setup):

```bash
# Add this function to ~/.bashrc or ~/.zshrc
with-proxy() {
    http_proxy=http://127.0.0.1:1081 \
    https_proxy=http://127.0.0.1:1081 \
    HTTP_PROXY=http://127.0.0.1:1081 \
    HTTPS_PROXY=http://127.0.0.1:1081 \
    all_proxy=socks5://127.0.0.1:1080 \
    ALL_PROXY=socks5://127.0.0.1:1080 \
    "$@"
}

# Reload shell
source ~/.zshrc  # or ~/.bashrc
```

**Usage:**

```bash
# Run any command through xray proxy
with-proxy curl https://ipinfo.io/ip
with-proxy claude chat
with-proxy k9s
with-proxy npm install
with-proxy git clone https://github.com/user/repo.git
with-proxy wget https://example.com/file.zip

# Works with any command-line tool
with-proxy python -m pip install package
with-proxy go get github.com/user/package
with-proxy docker pull image:tag
```

**Benefits:**
- Works with any CLI tool without configuration
- No need to remember different proxy settings for each tool
- Easy to enable/disable per command
- No system-wide changes required

### Option 2: Environment Variables (Terminal-wide)

Set proxy environment variables to make all terminal applications use the proxy:

```bash
# Add to ~/.bashrc or ~/.zshrc
export http_proxy=http://127.0.0.1:1081
export https_proxy=http://127.0.0.1:1081
export HTTP_PROXY=http://127.0.0.1:1081
export HTTPS_PROXY=http://127.0.0.1:1081
export all_proxy=socks5://127.0.0.1:1080
export ALL_PROXY=socks5://127.0.0.1:1080

# Reload shell config
source ~/.bashrc  # or ~/.zshrc

# Test
curl https://ipinfo.io/ip
```

**Note**: This only affects terminal applications, not GUI applications.

### Option 3: System Proxy Settings (GUI Applications)

#### Ubuntu/GNOME:
```bash
# Set system-wide proxy
gsettings set org.gnome.system.proxy mode 'manual'
gsettings set org.gnome.system.proxy.socks host '127.0.0.1'
gsettings set org.gnome.system.proxy.socks port 1080

# Or use GUI: Settings → Network → Network Proxy → Manual
# Set SOCKS Host: 127.0.0.1, Port: 1080
```

#### KDE Plasma:
```
System Settings → Network → Proxy → Manual
SOCKS Proxy: 127.0.0.1:1080
```

### Option 4: Proxychains (Per-Application Transparent Proxy)

Install and configure proxychains to transparently proxy any application:

```bash
# Install
sudo apt install proxychains4  # Ubuntu/Debian
sudo dnf install proxychains-ng  # Fedora

# Configure
sudo nano /etc/proxychains4.conf

# Add to end of file (comment out other proxy_list entries):
[ProxyList]
socks5 127.0.0.1 1080

# Use with any application
proxychains4 firefox
proxychains4 telegram-desktop
proxychains4 wget https://example.com
```

### Option 5: Transparent Proxy with iptables (Advanced)

For true system-wide transparent proxy (like TUN mode), use redsocks:

```bash
# Install redsocks
sudo apt install redsocks

# Configure redsocks
sudo nano /etc/redsocks.conf

# Basic config:
base {
    log_debug = off;
    log_info = on;
    daemon = on;
    redirector = iptables;
}

redsocks {
    local_ip = 127.0.0.1;
    local_port = 12345;
    ip = 127.0.0.1;
    port = 1080;
    type = socks5;
}

# Start redsocks
sudo systemctl start redsocks

# Set up iptables rules (run as root)
sudo iptables -t nat -N REDSOCKS
sudo iptables -t nat -A REDSOCKS -d 0.0.0.0/8 -j RETURN
sudo iptables -t nat -A REDSOCKS -d 10.0.0.0/8 -j RETURN
sudo iptables -t nat -A REDSOCKS -d 127.0.0.0/8 -j RETURN
sudo iptables -t nat -A REDSOCKS -d 169.254.0.0/16 -j RETURN
sudo iptables -t nat -A REDSOCKS -d 172.16.0.0/12 -j RETURN
sudo iptables -t nat -A REDSOCKS -d 192.168.0.0/16 -j RETURN
sudo iptables -t nat -A REDSOCKS -d 224.0.0.0/4 -j RETURN
sudo iptables -t nat -A REDSOCKS -d 240.0.0.0/4 -j RETURN
sudo iptables -t nat -A REDSOCKS -p tcp -j REDIRECT --to-ports 12345
sudo iptables -t nat -A OUTPUT -p tcp -j REDSOCKS

# To remove rules later:
sudo iptables -t nat -F REDSOCKS
sudo iptables -t nat -D OUTPUT -p tcp -j REDSOCKS
sudo iptables -t nat -X REDSOCKS
```

**⚠️ Warning**: Transparent proxy requires root privileges and can break local network access if misconfigured.

### Recommended Approach

For most users:
- **Any CLI tool** (easiest): Use `with-proxy` function (Option 1) - **Recommended!**
- **All terminal apps**: Use environment variables (Option 2)
- **GUI applications**: Configure each app individually or use system proxy settings (Option 3)
- **Specific applications**: Use proxychains (Option 4)
- **System-wide**: Use redsocks with iptables (Option 5) - advanced users only

**Quick Comparison:**

| Method | Ease of Use | Scope | Example |
|--------|-------------|-------|---------|
| with-proxy | ⭐⭐⭐⭐⭐ Easiest | Per command | `with-proxy claude chat` |
| Environment vars | ⭐⭐⭐⭐ Easy | Terminal session | `export http_proxy=...` |
| System settings | ⭐⭐⭐ Medium | GUI apps | Settings → Network |
| Proxychains | ⭐⭐⭐ Medium | Per app | `proxychains4 app` |
| Redsocks | ⭐ Advanced | System-wide | Requires root |

## Configuration

Configuration is stored in `~/.xray-client/`:

```
~/.xray-client/
├── config.json           # Main configuration (servers, subscriptions, settings)
├── bin/xray              # xray-core binary (auto-downloaded)
├── running_config.json   # Current xray configuration
├── xray.pid              # Process ID file
└── logs/
    ├── xray.log          # xray-core output log
    └── xray_error.log    # xray-core error log
```

### Configuration File Structure

```json
{
  "version": "1.0",
  "current_server": "server-id",
  "servers": [...],
  "subscriptions": [...],
  "settings": {
    "local_socks_port": 1080,
    "local_http_port": 1081,
    "auto_update_subscriptions": true,
    "update_interval_hours": 24,
    "log_level": "warning"
  }
}
```

### Changing Default Ports

Edit `~/.xray-client/config.json` and modify the `settings` section:

```json
"settings": {
  "local_socks_port": 10808,
  "local_http_port": 10809
}
```

## Application-Specific Configuration

### Using with-proxy Function (Easiest)

For any CLI tool, simply prefix with `with-proxy`:

```bash
# Claude CLI
with-proxy claude chat
with-proxy claude --model opus chat

# Kubernetes tools
with-proxy k9s
with-proxy kubectl get pods
with-proxy helm install myapp ./chart

# Development tools
with-proxy npm install
with-proxy pip install package
with-proxy go get github.com/user/package
with-proxy cargo build

# Git operations
with-proxy git clone https://github.com/user/repo.git
with-proxy git pull origin main

# Package managers
with-proxy apt update  # (with sudo: sudo -E with-proxy apt update)
with-proxy brew install package

# Any other CLI tool
with-proxy curl https://api.example.com
with-proxy wget https://example.com/file.zip
with-proxy docker pull nginx:latest
```

### Firefox
1. Settings → General → Network Settings
2. Select "Manual proxy configuration"
3. SOCKS Host: `127.0.0.1`, Port: `1080`
4. Select "SOCKS v5"
5. Check "Proxy DNS when using SOCKS v5"

### Chrome/Chromium
```bash
google-chrome --proxy-server="socks5://127.0.0.1:1080"
```

### Telegram Desktop
1. Settings → Advanced → Connection type
2. Use custom proxy → SOCKS5
3. Host: `127.0.0.1`, Port: `1080`

### Git
```bash
git config --global http.proxy socks5://127.0.0.1:1080
git config --global https.proxy socks5://127.0.0.1:1080

# To unset later
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### npm
```bash
npm config set proxy http://127.0.0.1:1081
npm config set https-proxy http://127.0.0.1:1081

# To unset later
npm config delete proxy
npm config delete https-proxy
```

### Docker
Add to `~/.docker/config.json`:
```json
{
  "proxies": {
    "default": {
      "httpProxy": "http://127.0.0.1:1081",
      "httpsProxy": "http://127.0.0.1:1081"
    }
  }
}
```

## Troubleshooting

### Connection Issues

```bash
# Check if xray is running
uv run xray-client status

# View logs
tail -f ~/.xray-client/logs/xray.log
tail -f ~/.xray-client/logs/xray_error.log

# Test server connectivity
uv run xray-client test "server-id"

# Reconnect
uv run xray-client disconnect
uv run xray-client connect "server-name"
```

### Binary Issues

```bash
# Check xray version
~/.xray-client/bin/xray version

# Re-download xray binary
rm -rf ~/.xray-client/bin/
uv run xray-client connect "server-name"  # Will auto-download
```

### Subscription Issues

```bash
# Update with verbose output
uv run xray-client subscribe update

# Check subscription format
curl "your-subscription-url" | base64 -d
```

## Architecture

```
src/
├── cli/
│   └── main.py              # CLI entry point (Click framework)
├── core/
│   ├── binary_manager.py    # Download and manage xray-core
│   ├── config.py            # Configuration file management
│   ├── config_generator.py  # Generate xray-core JSON configs
│   ├── process_manager.py   # Subprocess lifecycle management
│   └── subscription.py      # Subscription fetching and parsing
├── parsers/
│   ├── base.py              # Base parser class
│   ├── vless.py             # VLESS link parser
│   └── vmess.py             # VMess link parser
└── utils/
    ├── helpers.py           # Helper functions
    └── latency.py           # Server latency testing
```

## Supported Protocols

- **VLESS**: Full support including XTLS flow control and REALITY
- **VMess**: Full support with alterID

## Supported Transports

- TCP
- WebSocket (WS)
- gRPC
- HTTP/2
- QUIC

## Supported Security

- None (plain)
- TLS
- XTLS (with flow control)
- REALITY

## CLI Reference

```
xray-client --help                          Show help message
xray-client --version                       Show version

xray-client connect <name|id>               Connect to server
xray-client disconnect                      Disconnect current connection
xray-client status                          Show connection status

xray-client list [--sort-by name|protocol]  List all servers
xray-client add <link> [--name NAME]        Add server from link
xray-client remove <id>                     Remove server

xray-client subscribe add <name> <url>      Add subscription
xray-client subscribe update [name]         Update subscription(s)
xray-client subscribe list                  List subscriptions
xray-client subscribe remove <name>         Remove subscription

xray-client test [id] [--timeout SECONDS]   Test server latency
```

## Development

```bash
# Install in development mode
uv sync

# Run tests (when implemented)
pytest

# Format code
isort src && black src/

# Type checking
mypy src/
```

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built on [xray-core](https://github.com/XTLS/Xray-core)
- Compatible with standard V2Ray/Xray subscription format
- Supports Marzban, v2raytun, and other subscription providers

---

## 🚀 Quick Reference: Using with-proxy

**The easiest way to use xray-client with any CLI tool:**

Once connected, simply prefix any command with `with-proxy`:

```bash
# Connect to VPN first
uv run xray-client connect "server-name"

# Then use with-proxy with any command
with-proxy curl https://ipinfo.io/ip
with-proxy claude chat
with-proxy k9s
with-proxy kubectl get pods
with-proxy npm install
with-proxy git clone https://github.com/user/repo.git
with-proxy docker pull nginx:latest
```

**How it works:**
- The `with-proxy` function is automatically added to your `~/.zshrc` (or `~/.bashrc`)
- It sets proxy environment variables for that specific command
- No system-wide changes or per-app configuration needed
- Works with virtually any CLI tool

**Manual setup (if not already added):**

```bash
# Add to ~/.zshrc or ~/.bashrc
with-proxy() {
    http_proxy=http://127.0.0.1:1081 \
    https_proxy=http://127.0.0.1:1081 \
    HTTP_PROXY=http://127.0.0.1:1081 \
    HTTPS_PROXY=http://127.0.0.1:1081 \
    all_proxy=socks5://127.0.0.1:1080 \
    ALL_PROXY=socks5://127.0.0.1:1080 \
    "$@"
}

# Reload
source ~/.zshrc
```

**Alternative methods:**
- For system-wide proxy, see [System-Wide Proxy Setup](#system-wide-proxy-setup) section above
- For GUI applications, see [Application-Specific Configuration](#application-specific-configuration) section

---

## Support

For issues, questions, or contributions, please open an issue on GitHub.
