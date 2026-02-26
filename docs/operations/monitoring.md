# Monitoring

FlowGate writes operational events and performance metrics to the configured events log (see `paths.log_file`).

Recommended workflow:

1. Start services: `flowgate service start all`
2. Check: `flowgate health --verbose`
3. Inspect events log: the JSON lines file under `paths.log_file`

