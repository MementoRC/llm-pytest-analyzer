# Pytest-Analyzer Architecture Review

## 1. Executive Summary


This report provides an automated analysis of the `pytest-analyzer` codebase architecture.
It covers module dependencies, circular references, interface design, and code maintainability.
The goal is to identify architectural strengths, weaknesses, and provide actionable
recommendations for improvement.

## 2. Dependency Analysis

Analyzed **143** modules inside `src/pytest_analyzer` using **manual (AST)**.

### Highest Fan-Out (Most Coupled Modules)

| Module | Outgoing Dependencies |
|---|---|

| `pytest_analyzer.core.di.service_collection` | 17 |

| `pytest_analyzer.core.analyzer_facade` | 13 |

| `pytest_analyzer.core.analyzer_service` | 13 |

| `pytest_analyzer.mcp.facade` | 13 |

| `pytest_analyzer.core.analyzer_service_di` | 11 |


### Highest Fan-In (Most Depended-On Modules)

| Module | Incoming Dependencies |
|---|---|

| `pytest_analyzer.core.models.pytest_failure` | 28 |

| `pytest_analyzer.core.errors` | 17 |

| `pytest_analyzer.utils.settings` | 17 |

| `pytest_analyzer.utils.resource_manager` | 14 |

| `pytest_analyzer.core.llm.llm_service_protocol` | 14 |


### Architectural Layering Violations

**WARNING**: Found dependencies from `core` layers to outer layers (`cli`, `mcp`). This violates the Dependency Rule and should be fixed.


- `pytest_analyzer.core.analyzer_service` -> `pytest_analyzer.cli.analyzer_cli`
- `pytest_analyzer.core.analyzer_service_state_machine` -> `pytest_analyzer.cli.analyzer_cli`
- `pytest_analyzer.core.analyzer_service_di` -> `pytest_analyzer.cli.analyzer_cli`

## 3. Circular Dependency Check

**CRITICAL: Found 3 circular dependency groups.** These create tight coupling and can lead to import errors and maintenance issues.


### Cycle 1

```
pytest_analyzer.cli.analyzer_cli ->
pytest_analyzer.cli.mcp_cli ->
pytest_analyzer.core.analyzer_facade ->
pytest_analyzer.core.di.service_collection ->
pytest_analyzer.core.analyzer_service_di ->
pytest_analyzer.cli.analyzer_cli
```


### Cycle 2

```
pytest_analyzer.cli.analyzer_cli ->
pytest_analyzer.core.analyzer_service ->
pytest_analyzer.cli.analyzer_cli
```


### Cycle 3

```
pytest_analyzer.core.di.__init__ ->
pytest_analyzer.core.di.decorators ->
pytest_analyzer.core.di.__init__
```


**Recommendation**: Break these cycles by using dependency inversion (e.g., introducing a `Protocol`), moving shared functionality to a new, lower-level module, or refactoring responsibilities.


## 4. Interface and Contract Review (SOLID Principles)

Found **10** `Protocol` definitions, which supports the **Dependency Inversion Principle**.


No 'fat' interfaces detected. Protocols appear well-scoped, adhering to the **Interface Segregation Principle**.


## 5. Maintainability Metrics (Radon)

Maintainability analysis could not be performed.


## 6. Summary of Recommendations

1. **High Priority**: Refactor modules to break all identified circular dependencies. This is critical for a healthy architecture.
4. **High Priority**: Fix architectural layering violations. The `core` should not depend on `cli` or `mcp`. Use dependency inversion to pass information outwards.
