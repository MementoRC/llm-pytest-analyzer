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

### Current GUI Enhancement Project

#### Status - Task 6 COMPLETED ✅
- **Current Phase**: Live Test Output Display implemented successfully
- **PRD Location**: `scripts/gui_enhancement_prd.txt`
- **Task List**: `tasks/gui_tasks.json` (managed by taskmaster-ai)
- **Progress**: 6/20 tasks complete (30%)
- **PR #8**: All CI checks passing ✅

#### Task 1 Achievement: MVC Controller Architecture
**Successfully implemented complete controller architecture:**
- ✅ **BaseController**: Abstract base with common functionality
- ✅ **FileController**: File loading and report parsing (JSON/XML)
- ✅ **TestResultsController**: Test selection and results management
- ✅ **AnalysisController**: Test execution/analysis coordination (placeholders)
- ✅ **SettingsController**: Configuration management (placeholder)
- ✅ **MainController**: Main orchestration and signal routing

#### Task 2 Achievement: Background Task Management
**Successfully implemented Qt QThread-based background task system:**
- ✅ **TaskManager**: QObject-based task orchestration and queue management
- ✅ **WorkerThread**: QThread-based task execution with progress reporting
- ✅ **ProgressBridge**: Bridge between Rich progress and Qt signals
- ✅ **Controller Integration**: Enhanced all controllers with background task support
- ✅ **AnalysisController**: Fully implemented test execution and LLM analysis

#### Task 3 Achievement: PytestAnalyzerService Integration
**Successfully integrated core test execution service with GUI:**
- ✅ **Enhanced AnalysisController**: Full file and directory test execution support
- ✅ **Extended TestResultsModel**: Suggestion storage and analysis status tracking
- ✅ **Bidirectional Conversion**: Seamless data conversion between service and GUI
- ✅ **Real-time Progress**: Background execution with progress reporting
- ✅ **Analysis Integration**: LLM analysis workflow with suggestion management

#### Task 4 Achievement: Test Discovery and Selection UI
**Successfully implemented test discovery interface:**
- ✅ **TestDiscoveryView**: Tree-based test hierarchy display
- ✅ **TestDiscoveryController**: Test discovery and selection management
- ✅ **Checkbox Selection**: Individual and batch test selection
- ✅ **Search Filtering**: Quick test location functionality
- ✅ **Pytest Integration**: Seamless pytest test collection

#### Task 5 Achievement: Test Execution Progress Tracking
**Successfully implemented progress tracking:**
- ✅ **TestExecutionProgressView**: Real-time progress display
- ✅ **Progress Indicators**: Overall progress bar and status counts
- ✅ **Time Tracking**: Elapsed time and test counts
- ✅ **Cancel Support**: Ability to stop running tests
- ✅ **State Management**: Proper handling of execution states

#### Task 6 Achievement: Live Test Output Display
**Successfully implemented test output streaming:**
- ✅ **TestOutputView**: Real-time output display widget
- ✅ **Syntax Highlighting**: Python traceback highlighting
- ✅ **Output Filtering**: All Output/Errors Only modes
- ✅ **Autoscroll Toggle**: User-controlled scrolling
- ✅ **Copy Functionality**: Easy output sharing

**Architecture Benefits Achieved:**
- Complete test execution workflow in GUI
- File and directory test execution support
- Real-time progress feedback during execution
- Live output streaming during test runs
- Enhanced data model with suggestion support
- Seamless integration with existing background task system
- All tests passing (11 GUI tests, 15% overall coverage)

#### GUI Development Tasks Overview
1. **Phase 1**: ✅ Controller Architecture, ✅ Background Tasks, ✅ Test Execution, ✅ Test Discovery, ✅ Progress Tracking, ✅ Live Output
2. **Phase 2**: LLM Analysis Integration (In Progress - Task 7)
3. **Phase 3**: Fix Application Workflow
4. **Phase 4**: Settings & Project Management
5. **Phase 5**: Advanced Features

#### Next: Task 7 - Automatic Test Results Loading
Ready to implement automatic loading and display of test results after execution completes.

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
Task 6 (Live Test Output Display) completed successfully with all CI checks passing. 
Ready to proceed with Task 7 (Automatic Test Results Loading) to continue Phase 2 of GUI development.

Remember: 
- Use aider for complex code implementations
- Always run quality checks after changes
- Create git branches for each major feature
- Keep this CLAUDE.md updated with project evolution