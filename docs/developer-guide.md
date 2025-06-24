# Developer Guide

This guide provides essential information for developers contributing to or maintaining the `pytest-analyzer` project.

---

## 1. Getting Started

- Clone the repository and install dependencies using the recommended environment manager (Pixi, Poetry, etc.).
- Review the [Architecture](architecture.md) and [API User Guide](api-user-guide.md) for an overview of the system.

## 2. Code Structure

- **src/pytest_analyzer/**: Core modules (extraction, analysis, suggestion, application, CLI, utils)
- **src/llm_task_framework/**: LLM task framework and registry
- **docs/**: Documentation
- **tests/**: Test suite

## 3. Development Workflow

- Use feature branches and submit pull requests for review.
- Write unit and integration tests for all new features.
- Run static analysis (`bandit`, `flake8`, `mypy`) and dependency checks (`safety`) before merging.
- Update documentation for all user-facing changes.

## 4. Dependency Injection & Extensibility

- Register new services and implementations in the DI container.
- Use protocol-based interfaces for new components.
- See [Dependency Injection](DEPENDENCY_INJECTION.md) for details.

## 5. Security

- Follow the [Security Practices Guide](security-practices.md).
- Never commit secrets or sensitive data.
- Validate all inputs and sanitize file paths.

## 6. Testing

- Run the full test suite with `pytest`.
- Add security and edge case tests for new features.
- Use mocks and DI for isolated testing.

## 7. Documentation

- Update or add documentation in the `docs/` directory.
- Build and preview docs locally with `mkdocs serve`.

## 8. Release Process

- Update the changelog and version.
- Tag releases and publish to PyPI as appropriate.
- Announce new releases and document major changes.

---

## Resources

- [Architecture](architecture.md)
- [API User Guide](api-user-guide.md)
- [Security Practices](security-practices.md)
- [Operations Guide](operations-guide.md)
- [Disaster Recovery](disaster-recovery.md)
- [Project Retrospective](project-retrospective.md)
