# Upgrade Procedures

## FlowGate

- Upgrade your checkout / package
- Run `uv sync` to align dependencies
- Run `flowgate doctor` to validate runtime artifacts and credentials

## CLIProxyAPIPlus

Use:

```bash
flowgate --config config/flowgate.yaml bootstrap update
```

