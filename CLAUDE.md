# Claude Code Instructions for pytest-analyzer

## Project Overview
This is a pytest failure analysis tool that uses LLM services to suggest and apply fixes for failing tests. The project has both CLI and GUI interfaces with a comprehensive architecture using dependency injection and state machines.

## Development Workflow

### Quality Assurance Commands
Always run these commands to maintain code quality:

```bash
# Pre-commit checks (run frequently)
pixi run -e dev pre-commit run --all-files

# Test suite (run after changes)  
pixi run -e dev pytest

# GUI-specific tests
pixi run -e dev pytest tests/gui/ -v

# Full test suite with coverage
pixi run -e dev pytest --cov=src/pytest_analyzer --cov-report=html
```

### Aider-Focused Development Approach

#### Tool Priorities
1. **USE AIDER EXTENSIVELY**: Primary tool for ALL code operations
2. **Architect Mode**: Use `--architect` for complex implementations
3. **Token Conservation**: Delegate coding to aider, focus on orchestration
4. **Quality First**: Always validate with pre-commit and pytest

#### Git Safety Protocol (CRITICAL)
```bash
# ALWAYS create dedicated branches for aider work
git checkout -b aider/<feature-name>

# Commit work before aider
git add . && git commit -m "WIP: Before aider implementation"

# After aider, show changes
git diff

# Run quality checks
pixi run -e dev pre-commit run --all-files
pixi run -e dev pytest
```

#### Aider Command Patterns

**Basic Implementation:**
```bash
aider --model gemini/gemini-2.5-pro-preview-05-06 --no-stream --yes file1.py file2.py
```

**Complex Architecture (use for major features):**
```bash
aider --architect --model gemini/gemini-2.5-pro-preview-05-06 --no-stream --yes --no-pretty context_files...
```

**After Aider - Always Show Changes:**
```bash
git diff -- <modified-files>
```

### Current GUI Enhancement Project

#### Status
- **Current Phase**: Implementing controller architecture (Task 1 of 20)
- **PRD Location**: `scripts/gui_enhancement_prd.txt`
- **Task List**: `tasks/gui_tasks.json` (managed by taskmaster-ai)

#### GUI Development Tasks Overview
1. **Phase 1**: Controller Architecture, Background Tasks, Test Execution
2. **Phase 2**: LLM Analysis Integration  
3. **Phase 3**: Fix Application Workflow
4. **Phase 4**: Settings & Project Management
5. **Phase 5**: Advanced Features

### Project Structure
```
src/pytest_analyzer/
├── cli/                    # Command-line interface
├── core/                   # Core business logic
│   ├── analysis/          # Failure analysis components
│   ├── di/                # Dependency injection
│   ├── extraction/        # Test result extractors
│   ├── llm/               # LLM service integration
│   └── state_machine/     # Workflow state management
├── gui/                   # GUI application
│   ├── controllers/       # MVC controllers (being implemented)
│   ├── models/           # Data models
│   └── views/            # UI components
└── utils/                # Utilities and configuration
```

### Integration Points
The GUI controllers need to integrate with these core services:
- `PytestAnalyzerService`: Main analysis orchestration
- `AnalyzerStateMachine`: Workflow management
- `LLMSuggester`: AI-powered analysis
- `FixApplier`: Code modification
- `ConfigurationManager`: Settings

### Quality Standards
- **Type Checking**: All code must pass mypy
- **Linting**: Must pass ruff checks
- **Formatting**: Auto-formatted with ruff
- **Testing**: Maintain high test coverage
- **Documentation**: Docstrings for all public interfaces

### Environment Setup
```bash
# Package management through pixi
pixi install

# Development environment
pixi shell -e dev

# GUI testing requires Qt
export QT_QPA_PLATFORM=offscreen  # For headless testing
```

### API Keys Required
- `OPENAI_API_KEY`: For OpenAI LLM services
- `ANTHROPIC_API_KEY`: For Anthropic/Claude services  
- `GEMINI_API_KEY`: For Google Gemini services (used by aider)

### Common Issues
1. **Aider Authentication**: Ensure GEMINI_API_KEY is set
2. **Qt Testing**: Use `QT_QPA_PLATFORM=offscreen` for headless tests
3. **Pre-commit Hooks**: May modify files; commit again after fixes
4. **Token Usage**: Prefer aider for implementation, Claude for planning

### Next Steps
Currently implementing GUI controller architecture. After completing Task 1, proceed with taskmaster-ai managed tasks in priority order.

Remember: 
- Use aider for complex code implementations
- Always run quality checks after changes
- Create git branches for each major feature
- Keep this CLAUDE.md updated with project evolution