# Operations & Maintenance Guide

This guide provides best practices and procedures for operating and maintaining the `pytest-analyzer` system in production and development environments.

---

## 1. Deployment

- Deploy using a virtual environment or supported environment manager (Pixi, Poetry, Hatch, UV, Pipenv).
- Install dependencies using the lock file to ensure reproducibility.
- Use environment variables or a secret manager for sensitive configuration.

## 2. Configuration

- Project and user configuration can be set in `.pytest-analyzer.yaml` or `.pytest-analyzer.json`.
- Key settings: environment manager, LLM integration, resource limits, security options.
- Validate configuration before deployment.

## 3. Running the Analyzer

- Use the CLI for most operations:
  `pytest-analyzer path/to/tests [options]`
- For automation, use the Python API.
- Monitor resource usage (CPU, memory) and adjust limits as needed.

## 4. Monitoring and Logging

- Enable and monitor audit and application logs.
- Integrate with centralized logging and monitoring systems (e.g., ELK, Prometheus).
- Set up alerts for failures, security events, and resource exhaustion.

## 5. Backup and Data Management

- Regularly back up configuration files, test results, and any persistent cache or state.
- Store backups securely and test restoration procedures.

## 6. Upgrades and Maintenance

- Review release notes before upgrading.
- Test upgrades in a staging environment.
- Run `safety check` and static analysis after upgrades.
- Rotate secrets and review access controls regularly.

## 7. Troubleshooting

- Check logs for errors and warnings.
- Use the `--debug` flag for verbose output.
- Validate environment manager detection and configuration.
- For LLM/API issues, check API keys and network connectivity.

## 8. Support and Community

- Report issues on the [GitHub repository](https://github.com/MementoRC/llm-pytest-analyzer).
- Consult the [API User Guide](api-user-guide.md) and [Architecture](architecture.md) for advanced troubleshooting.

---

## Quick Reference

| Task                | Command/Action                                 |
|---------------------|------------------------------------------------|
| Run analyzer        | `pytest-analyzer path/to/tests`                |
| Specify env manager | `--env-manager poetry`                         |
| Enable LLM          | `--use-llm --llm-api-key <key>`                |
| Check dependencies  | `safety check`                                 |
| View logs           | Check configured log directory or system logs   |
| Backup config       | Copy `.pytest-analyzer.yaml` to secure storage  |
| Restore config      | Copy backup to project root                     |
