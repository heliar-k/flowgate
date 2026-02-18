# C4 Level 2: Container Diagram

This diagram breaks FlowGate into deployable/runtime containers and their integrations.

```mermaid
C4Container
  title Container diagram for FlowGate local stack

  Person(operator, "Local Developer/Operator", "Operates and troubleshoots local routing runtime")
  System_Ext(codexClient, "Codex CLI", "OpenAI-compatible client")
  System_Ext(claudeClient, "Claude Code", "Anthropic-compatible client")
  System_Ext(githubReleases, "GitHub Releases API", "Release metadata and binaries")
  System_Ext(oauthProviders, "OAuth Providers", "Authorize Codex/Copilot accounts")
  System_Ext(upstreamLlmApis, "Upstream LLM APIs", "Provider APIs serving model inference")

  System_Boundary(flowgateSystem, "FlowGate Local Router Stack") {
    Container(cli, "FlowGate CLI", "Python 3.12 + argparse", "Parses commands and orchestrates runtime")
    Container(litellm, "LiteLLM Proxy", "litellm[proxy]", "Northbound OpenAI-compatible endpoint")
    Container(cliproxy, "CLIProxyAPIPlus", "Native binary", "OAuth-backed upstream proxy and management APIs")
    ContainerDb(runtimeFiles, ".router Runtime Files", "Local filesystem", "Active config, state, pids, process logs, auth artifacts")
    ContainerDb(configFiles, "Project Config Files", "YAML/JSON in config/", "Service commands, profiles, credentials, auth endpoints")
  }

  Rel(operator, cli, "Runs operational commands", "Shell CLI")
  Rel(cli, configFiles, "Reads and validates router configuration", "File I/O")
  Rel(cli, runtimeFiles, "Writes active profile/state/events/runtime assets", "File I/O")
  Rel(cli, githubReleases, "Downloads CLIProxyAPIPlus release asset", "GitHub REST/HTTPS")
  Rel(cli, litellm, "Starts/stops/restarts and probes readiness", "Subprocess + HTTP")
  Rel(cli, cliproxy, "Starts/stops/restarts and probes readiness", "Subprocess + HTTP")
  Rel(cli, cliproxy, "Calls OAuth auth-url/status endpoints", "JSON/HTTP")

  Rel(codexClient, litellm, "Sends model requests", "HTTP /v1")
  Rel(claudeClient, litellm, "Sends model requests", "HTTP")
  Rel(litellm, runtimeFiles, "Reads generated active config", "File I/O")
  Rel(litellm, cliproxy, "Routes provider traffic through local gateway", "HTTP /v1")
  Rel(litellm, upstreamLlmApis, "Calls direct custom upstream endpoints", "HTTPS")
  Rel(cliproxy, oauthProviders, "Performs OAuth flows", "HTTPS")
  Rel(cliproxy, upstreamLlmApis, "Forwards provider requests", "HTTPS")
```
