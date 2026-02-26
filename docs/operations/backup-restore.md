# Backup & Restore

Suggested backup targets:

- Your FlowGate config file (e.g. `config/flowgate.yaml`)
- Runtime auth artifacts (e.g. `../.router/auths/*.json` if you store them there)

Restore is typically just putting these files back and re-running:

```bash
flowgate --config config/flowgate.yaml profile set balanced
flowgate --config config/flowgate.yaml service start all
```

