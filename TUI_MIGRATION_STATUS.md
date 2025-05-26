# TUI Migration Status

## Current Focus: Rich/Textual TUI Migration

**Last Updated**: Today  
**Phase**: Architecture Analysis → Rich/Textual Research

## Quick Context for Restart

### Problem Statement
- PyQt6/PySide6 GUI crashes on second test execution due to Qt memory management bugs
- Need stable TUI alternative for developer workflows

### Architecture Assessment ✅ COMPLETED
- **Core-GUI Separation**: Already achieved - `src/pytest_analyzer/core/` has zero Qt dependencies
- **Rich Integration**: Already present - CLI and core services use Rich progress bars
- **MVC Architecture**: Clean controller pattern ready for TUI adaptation
- **Background Tasks**: TaskManager can be adapted for async TUI event loops

### Current Task Status
Use `TodoRead` tool in Claude Code to see current migration task status.

**Key Tasks:**
1. ✅ Analyze GUI architecture and dependencies 
2. ✅ TUI foundation and testing infrastructure
3. ⏳ Controller integration with core services
4. 📋 Complete TUI views implementation
5. 📋 End-to-end workflow testing

### Key Files for Migration
- `gui_migration_proposals.md` - Full strategy document
- `CLAUDE.md` - Updated with TUI migration focus
- `src/pytest_analyzer/core/` - Core services (no changes needed)
- `src/pytest_analyzer/gui/controllers/` - Logic to adapt for TUI
- `src/pytest_analyzer/gui/views/` - Components to reimplement with Rich/Textual

### Next Steps
1. Integrate TUI controllers with core PytestAnalyzerService
2. Implement real functionality in TestExecutionController
3. Replace placeholder message handling with real events
4. Complete TUI views implementation (TestDiscoveryView, AnalysisResultsView)
5. End-to-end workflow testing

### Current Implementation Status
- ✅ TUI app foundation (src/pytest_analyzer/tui/app.py)
- ✅ Safe TUI testing infrastructure (tests/tui/)
- ✅ Controller skeleton and base classes
- ✅ View layout structure and placeholders
- ⏳ Controller integration with core services

### Migration Benefits
- No Qt framework dependencies
- Lightweight, fast interface
- Perfect for developer command-line workflows
- Leverages existing Rich integration
- Core services require zero changes