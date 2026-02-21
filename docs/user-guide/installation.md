# Installation Guide

This guide covers installing FlowGate and its dependencies on supported platforms.

## System Requirements

### Supported Platforms

- **macOS**: 11+ (Big Sur or later)
- **Linux**: Ubuntu 20.04+, Debian 11+, RHEL 8+, or compatible distributions
- **Python**: 3.11, 3.12, or 3.13
- **Architecture**: x86_64 (amd64) or ARM64 (arm64)

### Dependencies

FlowGate requires the following tools:

- **Python 3.11+**: Core runtime
- **uv**: Fast Python package manager ([astral.sh/uv](https://astral.sh/uv))
- **curl** or **wget**: For downloading runtime binaries
- **git** (optional): For development/contribution

## Installation Methods

### Method 1: Using uv (Recommended)

This is the fastest and most reliable installation method.

#### Step 1: Install uv

Follow the official uv installation guide: [docs.astral.sh/uv/getting-started/installation](https://docs.astral.sh/uv/getting-started/installation)

**Quick install** (macOS/Linux):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Or using Homebrew** (macOS):
```bash
brew install uv
```

#### Step 2: Clone the Repository

```bash
git clone https://github.com/heliar-k/flowgate.git
cd flowgate
```

#### Step 3: Install Dependencies

```bash
# Set UV cache directory (optional, improves performance)
export UV_CACHE_DIR=.uv-cache

# Install runtime and test dependencies
uv sync --group test --group dev
```

This creates a virtual environment at `.venv/` and installs:
- FlowGate package in editable mode
- LiteLLM proxy with dependencies
- Testing tools (pytest, pytest-cov)
- Documentation generator (pdoc)

#### Step 4: Verify Installation

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows (PowerShell)

# Check FlowGate version
flowgate --version

# Or use uv run without activating venv
uv run flowgate --version
```

Expected output:
```
flowgate, version 0.3.0
```

---

### Method 2: Using pip (Alternative)

If you prefer traditional pip-based installation:

#### Step 1: Create Virtual Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

#### Step 2: Install Package

```bash
pip install -e .
```

#### Step 3: Verify Installation

```bash
flowgate --version
```

---

## Post-Installation Setup

### 1. Create Configuration

```bash
# Create config directory
mkdir -p config

# Copy example configurations
cp config/examples/flowgate.yaml config/flowgate.yaml
cp config/examples/cliproxyapi.yaml config/cliproxyapi.yaml
```

### 2. Set Up Credentials

Create the secrets directory:

```bash
mkdir -p .router/secrets
chmod 700 .router/secrets
```

Add upstream API key (replace `sk-...` with your actual key):

```bash
printf '%s\n' "sk-YOUR_CLIPROXYAPI_KEY" > .router/secrets/upstream_cliproxyapi_api_key
chmod 600 .router/secrets/upstream_cliproxyapi_api_key
```

**Security note**: Never commit files in `.router/` to version control. This directory is gitignored by default.

### 3. Bootstrap Runtime Binaries

FlowGate requires platform-specific binaries for CLIProxyAPIPlus:

```bash
uv run flowgate --config config/flowgate.yaml bootstrap download
```

This downloads:
- **CLIProxyAPIPlus binary**: OAuth-enabled reverse proxy
- **LiteLLM runner script**: Wrapper for `uv run litellm`

Binaries are stored in `.router/bin/` and automatically detected by platform and architecture.

**Custom version** (optional):
```bash
uv run flowgate --config config/flowgate.yaml bootstrap download --cliproxy-version v6.8.18-1
```

**Updating to latest version** (recommended):
```bash
# Check for and apply updates (with confirmation prompt)
uv run flowgate --config config/flowgate.yaml bootstrap update

# Non-interactive update (skip confirmation)
uv run flowgate --config config/flowgate.yaml bootstrap update --yes
```

The `bootstrap update` command automatically:
- Checks GitHub for the latest CLIProxyAPIPlus version
- Prompts for confirmation (unless `--yes` is used)
- Downloads and validates the new binary
- Restarts the service if it's running

### 4. Run Preflight Checks

Verify your setup is correct:

```bash
uv run flowgate --config config/flowgate.yaml doctor
```

This checks:
- Configuration validity
- Runtime binaries exist
- Credentials are readable
- Required directories exist
- No port conflicts

Expected output:
```
✅ Configuration valid
✅ Runtime binaries present
✅ Credentials readable
✅ Directories ready
✅ Ports available (4000, 5000)

Doctor: System is ready
```

---

## Configuration Migration

If you're upgrading from FlowGate v0.1.x with `config_version: 1`:

### Check if Migration is Needed

```bash
uv run flowgate --config config/flowgate.yaml status
```

If you see a deprecation warning:
```
⚠️  WARNING: config_version 1 is deprecated and will be removed in v0.3.0
    Detected legacy fields: oauth
    Please run: flowgate config migrate
```

### Perform Migration

**Preview changes** (dry-run):
```bash
uv run flowgate --config config/flowgate.yaml config migrate --dry-run
```

**Apply migration** (creates automatic backup):
```bash
uv run flowgate --config config/flowgate.yaml config migrate
```

Backup location: `config/flowgate.yaml.backup-YYYYMMDD-HHMMSS`

See [Configuration Migration Guide](../developer-guide/config-version-migration.md) for details.

---

## Verification

After installation and setup, verify everything works:

### 1. Activate a Profile

```bash
uv run flowgate --config config/flowgate.yaml profile set balanced
```

Expected output:
```
✅ Profile 'balanced' activated
✅ Active config written to .router/runtime/active_config.yaml
```

### 2. Start Services

```bash
uv run flowgate --config config/flowgate.yaml service start all
```

Expected output:
```
✅ Service litellm started (PID: 12345)
✅ Service cliproxyapi_plus started (PID: 12346)
```

### 3. Check Health

```bash
uv run flowgate --config config/flowgate.yaml health
```

Expected output:
```
✅ LiteLLM: http://127.0.0.1:4000 (healthy)
✅ CLIProxyAPIPlus: http://127.0.0.1:5000 (healthy)
```

### 4. Stop Services

```bash
uv run flowgate --config config/flowgate.yaml service stop all
```

---

## Troubleshooting

### Common Issues

#### 1. `uv: command not found`

**Solution**: Install uv following [official docs](https://docs.astral.sh/uv/getting-started/installation)

#### 2. `ModuleNotFoundError: No module named 'flowgate'`

**Solution**: Ensure you activated the virtual environment or use `uv run`:
```bash
source .venv/bin/activate
# or
uv run flowgate --config config/flowgate.yaml <command>
```

#### 3. `Permission denied: .router/secrets/upstream_cliproxyapi_api_key`

**Solution**: Fix file permissions:
```bash
chmod 600 .router/secrets/upstream_cliproxyapi_api_key
chmod 700 .router/secrets
```

#### 4. `Port already in use: 4000`

**Solution**: Check for conflicting processes:
```bash
lsof -i :4000  # macOS/Linux
# Kill the process or change port in config/flowgate.yaml
```

#### 5. Bootstrap download fails with network error

**Solution**: Check internet connectivity and firewall settings. Try manual download:
```bash
# Download from GitHub releases manually
curl -L -o .router/bin/cliproxyapi \
  https://github.com/your-org/cliproxyapi/releases/download/v6.8.18-1/cliproxyapi-darwin-arm64
chmod +x .router/bin/cliproxyapi
```

### Getting More Help

If you encounter issues:

1. **Run diagnostics**:
   ```bash
   uv run flowgate --config config/flowgate.yaml doctor
   ```

2. **Check logs**:
   ```bash
   tail -n 50 .router/runtime/events.log
   ```

3. **Review troubleshooting guide**: [docs/user-guide/troubleshooting.md](troubleshooting.md)

4. **Report issues**: [github.com/heliar-k/flowgate/issues](https://github.com/heliar-k/flowgate/issues)

---

## Next Steps

After successful installation:

1. **Configure profiles**: [Profile Management Guide](profiles.md)
2. **Set up OAuth**: [Authentication Setup](authentication.md)
3. **Learn commands**: [CLI Reference](cli-reference.md)
4. **Explore configuration**: [Configuration Reference](configuration.md)

---

## Uninstallation

To completely remove FlowGate:

```bash
# Stop all services
uv run flowgate --config config/flowgate.yaml service stop all

# Remove virtual environment
rm -rf .venv

# Remove runtime artifacts (optional)
rm -rf .router

# Remove configuration (optional, keeps your settings)
# rm -rf config

# Remove repository (if cloned)
cd ..
rm -rf flowgate
```

**Note**: Credentials in `.router/secrets/` are permanently deleted. Back up any keys you want to keep.
