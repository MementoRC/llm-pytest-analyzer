# GUI Framework Migration Proposals

## Problem Statement

PyQt6 framework crashes during second test execution due to Qt internal resource management bugs, despite abundant system memory (4.7GB available, 155MB process usage). Investigation confirmed this is a Qt/PyQt6 framework limitation, not application memory issues.

**Current Issue**: GUI becomes unusable after first test run, making the tool unreliable for users.

## Migration Options (Prioritized by Implementation Effort)

### Immediate Solutions (1-2 Days)

#### 1. PySide6 Migration ⭐ RECOMMENDED FIRST
- **Effort**: 1-2 days
- **Risk**: Low
- **Description**: Switch from PyQt6 to PySide6 (Qt's official Python binding)
- **Benefits**: 
  - Minimal code changes (mostly import statements)
  - Same Qt API and functionality
  - May resolve PyQt6-specific framework bugs
  - Preserves all existing GUI architecture investment
- **Migration Strategy**: Update imports, dependencies, maintain existing MVC architecture

#### 2. Process Isolation Workaround
- **Effort**: Few hours
- **Risk**: Low
- **Description**: Add automatic GUI restart mechanism after each test run
- **Benefits**: 
  - Quick fix to work around Qt bugs
  - Preserves all existing functionality
  - Zero code changes to core logic
- **Drawbacks**: User experience degradation, hacky solution

### Medium-term Solutions (1-2 Weeks)

#### 3. Rich/Textual Terminal UI ⭐ ROBUST DEVELOPER SOLUTION
- **Effort**: 1-2 weeks
- **Risk**: Medium
- **Description**: Modern terminal interface using Rich/Textual frameworks
- **Benefits**:
  - Perfect for developer workflows
  - No GUI framework dependencies
  - Reuse all existing controller/service architecture
  - Lightweight and fast
  - Cross-platform compatibility
- **Migration Strategy**: Build TUI views that interface with existing controllers

#### 4. PyQt5 Downgrade
- **Effort**: 1-2 weeks
- **Risk**: Medium
- **Description**: Migrate to older, more stable PyQt5
- **Benefits**: Proven stability in production environments
- **Drawbacks**: Older framework, some API compatibility changes needed

### Long-term Solutions (3-4 Weeks)

#### 5. Web-based Interface
- **Effort**: 3-4 weeks
- **Risk**: High
- **Description**: FastAPI backend + modern web frontend (React/Vue)
- **Benefits**:
  - Cross-platform, stable, modern UX
  - No desktop framework dependencies
  - Best user experience potential
- **Drawbacks**: Complete rewrite, more complex deployment

#### 6. Hybrid Architecture
- **Effort**: 2-3 weeks
- **Risk**: Medium
- **Description**: Keep CLI as primary interface, add lightweight web dashboard
- **Benefits**: 
  - Minimal GUI surface area
  - Leverage existing CLI robustness
  - Progressive enhancement approach

## Implementation Strategy

### Phase 1: PySide6 Migration (Immediate)
1. **Core-GUI Separation**: Extract GUI dependencies from core logic
2. **Dependency Updates**: Replace PyQt6 with PySide6 in dependencies
3. **Import Migration**: Update all PyQt6 imports to PySide6
4. **Testing**: Validate functionality and crash behavior
5. **Fallback Preparation**: If crashes persist, implement process isolation

### Phase 2: Architecture Separation (During Migration)
To facilitate future migrations, implement clear separation:

#### Core Layer (GUI-Independent)
- `AnalyzerService`: Test execution and analysis
- `LLMSuggester`: AI-powered suggestions  
- `FixApplier`: Code modification
- `StateMachine`: Workflow management
- `Models`: Data structures and business logic

#### Interface Layer (GUI-Specific)
- `Controllers`: GUI event handling and coordination
- `Views`: UI components and widgets
- `Background`: Threading and progress management
- `Models`: GUI-specific data models

#### Abstraction Layer (New)
- `GUIProtocol`: Interface contract for GUI implementations
- `EventBus`: Decoupled communication between core and GUI
- `ViewModelAdapter`: Transform core data for UI consumption

### Phase 3: Fallback Options (If Needed)
If PySide6 migration doesn't resolve issues:
1. **Quick Fix**: Implement process isolation workaround
2. **Medium-term**: Begin Rich/Textual TUI development
3. **Long-term**: Consider web-based solution

## Technical Requirements

### Core-GUI Separation Principles
1. **No Direct GUI Dependencies in Core**: Core logic should work without any GUI framework
2. **Protocol-Based Interfaces**: Use protocols/interfaces for GUI communication
3. **Event-Driven Architecture**: Loose coupling through events/signals
4. **Testable Core**: All business logic testable without GUI
5. **Pluggable UI**: Easy to swap GUI implementations

### Migration Success Criteria
1. **No Second Test Run Crashes**: Primary requirement
2. **Feature Parity**: All existing functionality preserved
3. **Performance**: No performance degradation
4. **Maintainability**: Clean separation for future migrations
5. **Testing**: Comprehensive test coverage maintained

## Risk Mitigation

### PySide6 Migration Risks
- **Same Underlying Qt**: May have similar issues
- **API Differences**: Potential compatibility issues
- **Mitigation**: Quick fallback to process isolation if needed

### Core-GUI Separation Risks
- **Over-engineering**: Don't create unnecessary abstractions
- **Performance Impact**: Minimize overhead from abstraction layers
- **Mitigation**: Incremental refactoring, measure performance impact

## Timeline

### Week 1: PySide6 Migration + Core Separation
- Day 1-2: Update dependencies and imports
- Day 3-4: Extract core logic from GUI dependencies
- Day 5: Testing and validation

### Week 2: Fallback Implementation (If Needed)
- Day 1-2: Process isolation workaround
- Day 3-5: Begin Rich/Textual TUI prototype

## Success Metrics

1. **Stability**: No crashes on multiple consecutive test runs
2. **Usability**: All existing features functional
3. **Architecture**: Clear separation between core and GUI
4. **Future-Ready**: Easy migration path to alternative frameworks

---

**Next Steps**:
1. Update PR/CI status
2. Create new branch for PySide6 migration
3. Begin core-GUI separation during migration
4. Validate crash resolution with PySide6

**Fallback Plan**: If PySide6 doesn't resolve crashes, implement process isolation as immediate workaround while developing Rich/Textual TUI as robust long-term solution.