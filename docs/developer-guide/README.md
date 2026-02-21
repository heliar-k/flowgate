# Developer Guide

Welcome to the FlowGate Developer Guide! This section contains documentation for contributors and developers working on the FlowGate codebase.

## Contents

- **[Getting Started](getting-started.md)** - Set up your development environment
- **[Project Structure](project-structure.md)** - Understand the codebase organization
- **[Testing](testing.md)** - Testing guidelines and best practices
- **[Contributing](contributing.md)** - Contribution workflow and guidelines
- **[Config Internals](config-internals.md)** - Configuration system architecture
- **[Path Resolution](path-resolution.md)** - Path resolution technical reference
- **[Release Process](release-process.md)** - Release and rollback procedures
- **[Coding Standards](coding-standards.md)** - Code style and design patterns

## Quick Links

- [Architecture Overview](../architecture/README.md)
- [API Documentation](../api/README.md)
- [User Guide](../user-guide/README.md)

## Development Workflow

1. Fork and clone the repository
2. Set up development environment ([Getting Started](getting-started.md))
3. Make changes and write tests ([Testing](testing.md))
4. Submit pull request ([Contributing](contributing.md))
5. Code review and merge

## Useful Scripts

- **`scripts/xgate`**: FlowGate CLI 快捷启动脚本 (支持 `-h` 查看完整帮助)
- **`scripts/xtest`**: 测试运行快捷脚本 (支持 `-h` 查看 pytest 用法)
- **`scripts/smoke_local.sh`**: End-to-end smoke tests for all features
- **`scripts/security_check.sh`**: Security audit (tracked secrets, file permissions, gitignore)
- **`scripts/debug_cliproxyapi.sh`**: Debug CLIProxyAPIPlus service standalone
- **`scripts/generate_docs.sh`**: Generate API documentation with pdoc
- **`scripts/check_doc_links.py`**: Check markdown documentation for broken internal links

## Key Resources

- **CLAUDE.md / AGENTS.md**: AI assistant instructions (symlinked in root)
- **CI/CD**: `.github/workflows/ci.yml`
- **Test Suite**: `tests/` directory

---

**Target Audience**: Developers, contributors, maintainers

**Prerequisites**: Python 3.11+, Git, basic software engineering knowledge

For user-facing documentation, see the [User Guide](../user-guide/README.md).
