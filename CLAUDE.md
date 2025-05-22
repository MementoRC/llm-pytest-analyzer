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

#### Status - Task 1 COMPLETED ✅
- **Current Phase**: Controller Architecture implemented successfully
- **PRD Location**: `scripts/gui_enhancement_prd.txt`
- **Task List**: `tasks/gui_tasks.json` (managed by taskmaster-ai)
- **Progress**: 1/20 tasks complete (5%)

#### Task 1 Achievement: MVC Controller Architecture
**Successfully implemented complete controller architecture:**
- ✅ **BaseController**: Abstract base with common functionality
- ✅ **FileController**: File loading and report parsing (JSON/XML)
- ✅ **TestResultsController**: Test selection and results management
- ✅ **AnalysisController**: Test execution/analysis coordination (placeholders)
- ✅ **SettingsController**: Configuration management (placeholder)
- ✅ **MainController**: Main orchestration and signal routing

**Architecture Benefits Achieved:**
- Clean separation of concerns from MainWindow
- Proper MVC pattern with controller layer
- Signal/slot communication between components
- Ready for Tasks 2-20 implementation
- All tests passing (429 passed, 65% coverage)

#### GUI Development Tasks Overview
1. **Phase 1**: ✅ Controller Architecture, Background Tasks, Test Execution
2. **Phase 2**: LLM Analysis Integration  
3. **Phase 3**: Fix Application Workflow
4. **Phase 4**: Settings & Project Management
5. **Phase 5**: Advanced Features

#### Next: Task 2 - Background Task Management
Ready to implement Qt QThread-based background task system for long-running operations.

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

### Proven Task Implementation Methodology

#### Task 1 Success Pattern - Controller Architecture
**This methodology successfully delivered Task 1 and should be replicated for all future tasks:**

1. **Task Management Setup**
   ```bash
   # Mark task as in-progress in taskmaster-ai
   mcp__taskmaster-ai__set_task_status --id=1 --status=in-progress
   
   # Create dedicated git branch
   git checkout -b aider/<task-name>
   git add . && git commit -m "WIP: Before aider <task-name> implementation"
   ```

2. **Analysis Phase**
   ```bash
   # Use Claude Code Agent tool to analyze existing codebase
   # Understand current architecture, patterns, dependencies
   # Identify extraction points and integration requirements
   ```

3. **Aider Implementation**
   ```bash
   # Use architect mode for complex implementations
   aider --architect --model gemini/gemini-2.5-pro-preview-05-06 \
         --relative_editable_files=["new_files_to_create"] \
         --relative_readonly_files=["context_files_for_reference"]
   
   # Provide comprehensive prompts with:
   # - Clear requirements and specifications
   # - Integration points with existing code
   # - Type hints and documentation requirements
   # - Signal/slot patterns to follow
   ```

4. **Quality Validation**
   ```bash
   # ALWAYS run immediately after aider
   pixi run -e dev pre-commit run --all-files
   pixi run -e dev pytest tests/gui/ -v
   
   # Fix any issues found
   # Commit clean implementation
   git add . && git commit -m "Detailed implementation message"
   ```

5. **Task Completion**
   ```bash
   # Update taskmaster-ai status
   mcp__taskmaster-ai__set_task_status --id=1 --status=done
   
   # Update CLAUDE.md with progress
   # Document methodology improvements
   ```

**Key Success Factors:**
- **Comprehensive Context**: Provide aider with all relevant existing files
- **Detailed Prompts**: Specify exact requirements, patterns, and integration points
- **Quality First**: Never skip pre-commit and testing validation
- **Progressive Documentation**: Update CLAUDE.md after each major milestone
- **Signal/Slot Architecture**: Maintain Qt best practices for loose coupling

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