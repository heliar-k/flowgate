# Deployment

FlowGate is designed primarily for local developer/operator usage. If you run it on shared machines:

- Prefer binding services to `127.0.0.1`
- Restrict secret file permissions (`chmod 600`)
- Use a dedicated runtime directory per environment

See `docs/user-guide/installation.md` for setup basics.

