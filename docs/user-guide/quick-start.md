# Quick Start Guide

Get FlowGate up and running in **5 minutes**. This guide covers the essential steps to install, configure, and start using FlowGate.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** installed
- **uv** package manager ([install guide](https://docs.astral.sh/uv/getting-started/installation))
- **API key** for CLIProxyAPIPlus (or upstream provider)
- **macOS** or **Linux** system (Windows not officially supported)

## Step 1: Install FlowGate

Clone the repository and install dependencies:

```bash
# Clone repository
git clone https://github.com/heliar-k/flowgate.git
cd flowgate

# Install dependencies
export UV_CACHE_DIR=.uv-cache
uv sync --group test --group dev
```

**Estimated time**: 1-2 minutes

## Step 2: Configure

### 2.1 Copy Example Configurations

```bash
# Create config directory
mkdir -p config

# Copy templates
cp config/examples/flowgate.yaml config/flowgate.yaml
cp config/examples/cliproxyapi.yaml config/cliproxyapi.yaml
```

### 2.2 Set Up Credentials

Create a secrets directory and add your API key:

```bash
# Create secrets directory
mkdir -p .router/secrets
chmod 700 .router/secrets

# Add your upstream API key (replace sk-... with your actual key)
printf '%s\n' "sk-YOUR_CLIPROXYAPI_API_KEY" > .router/secrets/upstream_cliproxyapi_api_key
chmod 600 .router/secrets/upstream_cliproxyapi_api_key
```

**Security note**: The `.router/` directory is gitignored by default to prevent credential leaks.

### 2.3 Customize Configuration (Optional)

Edit `config/flowgate.yaml` to adjust:

- **Ports**: Default LiteLLM (4000) and CLIProxyAPIPlus (5000)
- **Profiles**: Customize `reliability`, `balanced`, `cost` strategies
- **Paths**: Runtime directories and log locations

See [Configuration Reference](configuration.md) for all options.

**Estimated time**: 2-3 minutes

## Step 3: Bootstrap Runtime

Download platform-specific binaries:

```bash
uv run flowgate --config config/flowgate.yaml bootstrap download
```

This downloads:
- **CLIProxyAPIPlus binary** for your platform (darwin/linux, amd64/arm64)
- **LiteLLM runner script** (wraps `uv run litellm`)

**Estimated time**: 30-60 seconds (depends on network speed)

## Step 4: Verify Setup

Run preflight checks:

```bash
uv run flowgate --config config/flowgate.yaml doctor
```

Expected output:
```
✅ Configuration valid
✅ Runtime binaries present
✅ Credentials readable
✅ Directories ready
✅ Ports available (4000, 5000)

Doctor: System is ready
```

If you see errors, consult the [Troubleshooting Guide](troubleshooting.md).

**Estimated time**: 10 seconds

## Step 5: Start Services

### 5.1 Activate a Profile

Choose a strategy profile:

```bash
# Options: reliability | balanced | cost
uv run flowgate --config config/flowgate.yaml profile set balanced
```

Expected output:
```
✅ Profile 'balanced' activated
✅ Active config written to .router/runtime/active_config.yaml
```

**Profile strategies**:
- **reliability**: Max retries, long timeouts (best for critical workloads)
- **balanced**: Moderate retries and timeouts (recommended default)
- **cost**: Minimal retries, fast fallbacks (cost-optimized)

### 5.2 Start All Services

```bash
uv run flowgate --config config/flowgate.yaml service start all
```

Expected output:
```
✅ Service litellm started (PID: 12345)
✅ Service cliproxyapi_plus started (PID: 12346)
```

### 5.3 Check Health

```bash
uv run flowgate --config config/flowgate.yaml health
```

Expected output:
```
✅ LiteLLM: http://127.0.0.1:4000 (healthy)
✅ CLIProxyAPIPlus: http://127.0.0.1:5000 (healthy)
```

**Estimated time**: 20-30 seconds

## Step 6: Test API Access

Now test the OpenAI-compatible endpoint:

```bash
curl http://127.0.0.1:4000/v1/models
```

Expected response (truncated):
```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-4",
      "object": "model",
      "created": 1234567890,
      "owned_by": "openai"
    },
    ...
  ]
}
```

### Make a Chat Completion Request

```bash
curl http://127.0.0.1:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

**Success!** 🎉 Your FlowGate instance is running.

---

## Common Tasks

### Switch Between Profiles

```bash
# Change to reliability profile
uv run flowgate --config config/flowgate.yaml profile set reliability

# Services automatically restart with new settings
```

### Check System Status

```bash
uv run flowgate --config config/flowgate.yaml status
```

Output shows:
- Current profile
- Service states (running/stopped)
- Configuration version
- Recent events

### Stop Services

```bash
# Stop all services
uv run flowgate --config config/flowgate.yaml service stop all

# Or stop individual services
uv run flowgate --config config/flowgate.yaml service stop litellm
uv run flowgate --config config/flowgate.yaml service stop cliproxyapi_plus
```

### Restart Services

```bash
# Restart all
uv run flowgate --config config/flowgate.yaml service restart all

# Restart individual service
uv run flowgate --config config/flowgate.yaml service restart litellm
```

### View Logs

```bash
# View event log
tail -f .router/runtime/events.log

# View service logs (if configured)
tail -f .router/runtime/logs/litellm.log
tail -f .router/runtime/logs/cliproxyapi_plus.log
```

---

## Integration with AI Clients

### Codex Integration

Generate integration snippet:

```bash
uv run flowgate --config config/flowgate.yaml integration print codex
```

Apply to Codex config:

```bash
uv run flowgate --config config/flowgate.yaml integration apply codex
```

### Claude Code Integration

Generate integration snippet:

```bash
uv run flowgate --config config/flowgate.yaml integration print claude-code
```

Apply to Claude Code config:

```bash
uv run flowgate --config config/flowgate.yaml integration apply claude-code
```

---

## OAuth Authentication (Optional)

If you're using OAuth providers (Codex, GitHub Copilot):

### Check Available Providers

```bash
uv run flowgate --config config/flowgate.yaml auth list
```

### Login to a Provider

```bash
# Start OAuth flow (opens browser)
uv run flowgate --config config/flowgate.yaml auth login codex --timeout 180

# Or import existing auth token (headless)
uv run flowgate --config config/flowgate.yaml auth import-headless codex --source ~/.codex/auth.json
```

### Verify Authentication

```bash
uv run flowgate --config config/flowgate.yaml auth status
```

See [Authentication Guide](authentication.md) for detailed OAuth setup.

---

## Convenience Scripts

FlowGate includes helper scripts in `scripts/`:

### xgate - Wrapper for flowgate CLI

```bash
# Instead of: uv run flowgate --config config/flowgate.yaml <command>
./scripts/xgate status
./scripts/xgate profile set reliability
./scripts/xgate service start all
```

### xtest - Run tests

```bash
# Run all unit tests
./scripts/xtest

# Run specific test file
./scripts/xtest tests/test_config.py
```

### smoke_local.sh - Integration test

```bash
# Test full stack with default profile
./scripts/smoke_local.sh config/flowgate.yaml

# Test specific profile
PROFILE=reliability ./scripts/smoke_local.sh config/flowgate.yaml
```

---

## Next Steps

Now that FlowGate is running, explore:

1. **[Profile Management](profiles.md)** - Understand strategy profiles and customization
2. **[Configuration Reference](configuration.md)** - Learn all configuration options
3. **[Authentication Setup](authentication.md)** - Set up OAuth providers
4. **[CLI Reference](cli-reference.md)** - Explore all available commands
5. **[Troubleshooting](troubleshooting.md)** - Debug common issues

---

## Troubleshooting Quick Tips

### Services won't start

```bash
# Check for port conflicts
lsof -i :4000
lsof -i :5000

# Check logs
tail -n 50 .router/runtime/events.log
```

### Health check fails

```bash
# Verify services are running
ps aux | grep litellm
ps aux | grep cliproxyapi

# Check PID files
cat .router/runtime/pids/litellm.pid
cat .router/runtime/pids/cliproxyapi_plus.pid
```

### Permission errors

```bash
# Fix secrets directory permissions
chmod 700 .router/secrets
chmod 600 .router/secrets/*

# Fix runtime directory
chmod 755 .router/runtime
```

### Configuration errors

```bash
# Validate configuration
uv run flowgate --config config/flowgate.yaml doctor

# Migrate legacy config (v1 → v2)
uv run flowgate --config config/flowgate.yaml config migrate
```

For detailed troubleshooting, see [Troubleshooting Guide](troubleshooting.md).

---

## Getting Help

- **Documentation**: [Complete Docs](../README.md)
- **CLI Help**: `uv run flowgate --help`
- **Command Help**: `uv run flowgate <command> --help`
- **Issue Tracker**: [github.com/heliar-k/flowgate/issues](https://github.com/heliar-k/flowgate/issues)
- **Architecture**: [Architecture Overview](../architecture/README.md)

---

## Summary

You've successfully:

✅ Installed FlowGate and dependencies
✅ Configured profiles and credentials
✅ Bootstrapped runtime binaries
✅ Started and verified services
✅ Tested API access

**Your FlowGate gateway is ready!** 🚀

Start experimenting with profile switching, OAuth authentication, and client integrations.
