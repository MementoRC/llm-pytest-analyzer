# Claude Code Instructions for pytest-analyzer

## Project Overview
This is a pytest failure analysis tool that uses LLM services to suggest and apply fixes for failing tests. The project has both CLI and GUI interfaces with a comprehensive architecture using dependency injection and state machines.

## Current Focus: TUI Migration Project 🚀

**ACTIVE TASK**: Migrating from PyQt6/PySide6 GUI to Rich/Textual TUI framework to resolve Qt memory issues causing crashes on second test run.

**Current Status**: TUI implementation in progress - foundation and testing infrastructure complete
**Task Tracking**: Use TodoRead/TodoWrite tools for current migration tasks
**Reference Documents**: 
- `gui_migration_proposals.md` - Migration strategy and options
- `TUI_MIGRATION_STATUS.md` - Quick status and context for restarts
- `ToDo.md` - General project tasks
- Current focus todos managed via TodoWrite/TodoRead tools

### TUI Migration Progress & Current Implementation Status

**✅ COMPLETED PHASES:**

1. **Architecture Analysis** (✅ DONE)
   - Core-GUI separation verified - no changes needed to `src/pytest_analyzer/core/`
   - Rich framework already integrated for progress bars and console output
   - Clean MVC controller pattern established

2. **TUI Foundation & Testing Infrastructure** (✅ DONE)
   - ✅ Textual TUI app structure in `src/pytest_analyzer/tui/`
   - ✅ Safe TUI testing with `tests/tui/` using pytest-asyncio
   - ✅ Headless testing verified - no terminal compromise
   - ✅ TUI controllers structure established
   - ✅ TUI views skeleton with placeholders

**⏳ CURRENT PHASE: Controller Integration**

Current task: Integrate TUI controllers with core services
- Connect FileController to PytestAnalyzerService
- Implement real TestExecutionController functionality
- Replace placeholder messages with real event handling

**📋 PENDING PHASES:**
4. Complete TUI views implementation (TestDiscoveryView, AnalysisResultsView, etc.)
5. End-to-end workflow testing

**Progress Tracking:**
```bash
# Check current migration status and specific tasks
TodoRead  # Use this tool in Claude Code for detailed task list
```

**Migration Rationale**: PyQt6 framework crashes during second test execution due to Qt internal resource management bugs. TUI provides stable, lightweight alternative perfect for developer workflows.

### TUI Migration Context & Restart Guide

**When restarting work on TUI migration:**

1. **Read Current Context**:
   ```bash
   # Check current migration status and todos
   TodoRead  # Use this tool in Claude Code
   ```

2. **Key Context Files**:
   - `gui_migration_proposals.md` - Full migration strategy and technical specifications
   - `TUI_MIGRATION_STATUS.md` - Quick status summary and restart context
   - `CLAUDE.md` (this file) - Development workflow and current focus
   - `src/pytest_analyzer/core/` - GUI-independent services (no changes needed)
   - `src/pytest_analyzer/gui/` - Current Qt implementation to migrate
   - `src/pytest_analyzer/tui/` - TUI implementation in progress
   - `tests/tui/` - Safe TUI testing infrastructure

3. **Current TUI Implementation Structure**:
   ```
   src/pytest_analyzer/tui/
   ├── app.py                    # Main TUIApp class (foundation complete)
   ├── controllers/              # Controller integration (IN PROGRESS)
   │   ├── main_controller.py    # Needs core service integration
   │   ├── file_controller.py    # Needs PytestAnalyzerService connection
   │   └── base_controller.py    # Foundation complete
   ├── views/                    # Views (placeholder → real implementation needed)
   │   ├── main_view.py          # Layout skeleton done
   │   ├── file_selection_view.py # Needs controller integration
   │   ├── test_execution_view.py # Needs real test execution
   │   └── test_results_view.py   # Needs real data integration
   └── events.py                 # Event system foundation
   
   tests/tui/                    # ✅ WORKING - Safe headless testing
   ├── conftest.py               # TUI test fixtures complete
   └── test_app.py               # Basic TUI tests passing
   ```

4. **TUI Testing Capabilities** (✅ COMPLETED):
   ```bash
   # Safe TUI testing - no terminal compromise
   pixi run -e dev pytest tests/tui/ -v
   
   # All TUI tests use headless mode via textual.run_test()
   # Key testing features:
   # - Mock analyzer service integration
   # - Safe key press simulation
   # - View loading verification
   # - No terminal state changes during testing
   ```

5. **Current Implementation Status**:
   - Phase 1: Architecture analysis ✅ COMPLETED
   - Phase 2: TUI foundation and testing infrastructure ✅ COMPLETED
   - Phase 3: Controller integration with core services ⏳ IN PROGRESS
   - Phase 4: Complete TUI views implementation 📋 PENDING
   - Phase 5: End-to-end workflow testing 📋 PENDING

## Development Workflow

### Quality Assurance Commands
Always run these commands to maintain code quality:

```bash
# Pre-commit checks (run frequently)
pixi run -e dev pre-commit run --all-files

# Test suite (run after changes)  
pixi run -e dev pytest

# GUI-specific tests (during migration period)
pixi run -e dev pytest tests/gui/ -v

# TUI-specific tests (safe headless testing)
pixi run -e dev pytest tests/tui/ -v

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
# Create dedicated aider branch for isolated work
git checkout feature/gui-interface
git checkout -b aider/<task-name>

# Commit work before aider (optional for safety)
git add . && git commit -m "WIP: Before aider <task-name> implementation" 

# After aider, show changes
git diff

# Run quality checks
pixi run -e dev pre-commit run --all-files
pixi run -e dev pytest

# Commit clean implementation to aider branch
git add . && git commit -m "Implement <task>: <details>"

# Merge to feature branch for PR progress
git checkout feature/gui-interface
git merge aider/<task-name> --no-ff

# Keep aider branch for safety/parallel work/exploration
# DON'T DELETE: git branch -D aider/<task-name>
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

### Current TUI Migration Project

**PRD Location**: `gui_migration_proposals.md` - Migration strategy and technical specifications  
**Task Management**: Use TodoRead/TodoWrite tools in Claude Code for current migration tasks
**Previous Project**: GUI Enhancement completed - now focusing on TUI migration to resolve Qt crashes

### Architectural Achievements

**✅ Core-GUI Separation Completed**
- Core logic (`src/pytest_analyzer/core/`) is completely GUI-framework agnostic
- Rich framework already integrated for progress bars and console output
- Clean separation enables easy TUI migration

**✅ MVC Controller Architecture** 
- BaseController: Abstract base with common functionality
- FileController: File loading and report parsing (JSON/XML)
- TestResultsController: Test selection and results management
- AnalysisController: Test execution/analysis coordination
- SettingsController: Configuration management
- MainController: Main orchestration and signal routing
- **TUI Migration**: Controllers can be adapted for TUI event handling

**✅ Background Task Management**
- TaskManager: QObject-based task orchestration and queue management
- WorkerThread: QThread-based task execution with progress reporting
- ProgressBridge: Bridge between Rich progress and Qt signals
- **TUI Migration**: TaskManager logic can be adapted for async TUI event loops

**✅ Test Execution Integration**
- PytestAnalyzerService: Full integration with core service (GUI-independent)
- Real-time Progress: Live updates during test execution (Rich-based)
- Output Streaming: Real-time stdout/stderr capture
- Automatic Results Loading: Results auto-load after execution
- **TUI Migration**: Core execution logic requires no changes

**🔄 GUI Components (To be migrated to TUI)**
- TestDiscoveryView → Rich tree display
- TestExecutionProgressView → Rich progress bars (already integrated)
- TestOutputView → Rich syntax highlighting
- TestResultsView → Rich tables and panels

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
The TUI interface will integrate with these core services (no changes needed):
- `PytestAnalyzerService`: Main analysis orchestration (GUI-independent)
- `AnalyzerStateMachine`: Workflow management (GUI-independent)
- `LLMSuggester`: AI-powered analysis (GUI-independent)
- `FixApplier`: Code modification (GUI-independent)
- `ConfigurationManager`: Settings (GUI-independent)

**TUI Migration Benefits**: All core services are already GUI-framework agnostic!

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
   
   # Create isolated aider branch from feature branch
   git checkout feature/gui-interface
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
   # Commit clean implementation to aider branch
   git add . && git commit -m "Implement Task X: Detailed implementation message"
   ```

5. **Task Completion & Integration**
   ```bash
   # Merge to feature branch for PR visibility
   git checkout feature/gui-interface
   git merge aider/<task-name> --no-ff
   
   # Update taskmaster-ai status
   mcp__taskmaster-ai__set_task_status --id=1 --status=done
   
   # Keep aider branch for safety and future exploration
   # Update CLAUDE.md with progress and methodology improvements
   ```

6. **CI Verification (CRITICAL)**
   ```bash
   # Push to remote to trigger CI
   git push origin feature/gui-interface
   
   # Check PR status
   gh pr list --head feature/gui-interface
   
   # Monitor CI checks (takes ~90s for tests to complete)
   gh pr checks <PR_NUMBER>
   
   # Wait for all checks to pass before proceeding to next task
   # Expected checks:
   # - lint_and_types (~30s)
   # - test (Python 3.9-3.12) (~90s each)
   # - CodeQL analysis (~90s)
   # - build-and-deploy (~10s)
   
   # If any checks fail, fix issues and repeat from step 4
   ```

**Key Success Factors:**
- **Comprehensive Context**: Provide aider with all relevant existing files
- **Detailed Prompts**: Specify exact requirements, patterns, and integration points
- **Quality First**: Never skip pre-commit and testing validation
- **Progressive Documentation**: Update CLAUDE.md after each major milestone
- **Signal/Slot Architecture**: Maintain Qt best practices for loose coupling

**Branching Strategy Benefits:**
- **Isolation**: Each aider/task-name branch isolates work safely
- **Parallel Development**: Multiple tasks can be worked on simultaneously  
- **Clean PR History**: feature/gui-interface shows clean progression
- **Rollback Safety**: Can revert to any aider branch if issues arise
- **Exploration**: Keep branches for trying alternative approaches
- **CI/CD Exercise**: Each merge to feature branch triggers CI pipeline

### Environment Setup
```bash
# Package management through pixi
pixi install

# Development environment
pixi shell -e dev

# GUI testing requires Qt (during migration period)
export QT_QPA_PLATFORM=offscreen  # For headless testing

# TUI testing (post-migration)
# No special environment variables needed
```

### API Keys Required
- `OPENAI_API_KEY`: For OpenAI LLM services
- `ANTHROPIC_API_KEY`: For Anthropic/Claude services  
- `GEMINI_API_KEY`: For Google Gemini services (used by aider)

### Common Issues
1. **Aider Authentication**: Ensure GEMINI_API_KEY is set
2. **Qt Testing**: Use `QT_QPA_PLATFORM=offscreen` for headless tests (during migration)
3. **Qt Memory Issues**: PyQt6/PySide6 crashes on second test run (reason for TUI migration)
4. **Pre-commit Hooks**: May modify files; commit again after fixes
5. **Token Usage**: Prefer aider for implementation, Claude for planning
6. **TUI Migration**: Use TodoRead tool to check current migration task status

### Working Framework Reminders

**Git Safety Protocol**
- Always create dedicated aider branches: `git checkout -b aider/<task-name>`
- Commit before aider work for safety
- Show diffs immediately after aider completes
- Run quality checks before merging

**Quality Standards**
- Pre-commit checks: `pixi run -e dev pre-commit run --all-files`
- GUI tests: `pixi run -e dev pytest tests/gui/ -v`
- All code must pass mypy, ruff, and formatting checks

**Aider Best Practices**
- Use architect mode for complex features
- Provide comprehensive file context (editable + readonly)
- Focus prompts on clear requirements and integration points
- Let aider handle implementation details