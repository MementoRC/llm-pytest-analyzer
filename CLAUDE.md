# Claude Development Framework Instructions

This document provides a reusable framework for managing complex software development projects using AI-assisted development tools and systematic project management.

## Framework Overview

This framework combines AI-assisted development with systematic project management using TaskMaster AI for tracking progress, maintaining quality standards, and ensuring systematic completion of complex software projects.

## Project Management with TaskMaster AI

### 🎯 **Task Management Strategy**

**Primary Tool**: Use the `taskmaster-ai` MCP tool for all project planning and tracking instead of manual markdown files.

**Core Commands**:
- `mcp__taskmaster-ai__initialize_project` - Set up project structure
- `mcp__taskmaster-ai__parse_prd` - Generate tasks from requirements document
- `mcp__taskmaster-ai__get_tasks` - View current project status
- `mcp__taskmaster-ai__next_task` - Get next prioritized task
- `mcp__taskmaster-ai__set_task_status` - Update task progress
- `mcp__taskmaster-ai__get_health_status` - Monitor project health

### Project Initialization Workflow

1. **Initialize TaskMaster Project**
   ```
   mcp__taskmaster-ai__initialize_project(projectRoot="/path/to/project")
   ```

2. **Create Requirements Document**
   - Place project requirements in `scripts/prd.txt`
   - Include technical specifications, objectives, and acceptance criteria

3. **Generate Task Structure**
   ```
   mcp__taskmaster-ai__parse_prd(input="scripts/prd.txt", numTasks="15")
   ```

4. **Monitor Progress**
   ```
   mcp__taskmaster-ai__get_tasks(withSubtasks=true)
   mcp__taskmaster-ai__next_task()
   ```

### Task Lifecycle Management

**Task Status Progression**:
- `pending` → `in-progress` → `done`
- Alternative: `pending` → `in-progress` → `review` → `done`
- Exception: `cancelled` or `deferred`

**Status Updates**:
```
mcp__taskmaster-ai__set_task_status(id="5", status="in-progress")
mcp__taskmaster-ai__set_task_status(id="5", status="done")
```

## Development Workflow Process

### 🎯 **SYSTEMATIC DEVELOPMENT WORKFLOW**

### Phase-Based Development

1. **Planning Phase**
   - Use TaskMaster AI to break down requirements into manageable tasks
   - Create dependency chains between tasks
   - Prioritize tasks based on complexity and dependencies
   - Set up quality gates and acceptance criteria

2. **Implementation Phase**
   - Follow task dependencies using `mcp__taskmaster-ai__next_task`
   - Update task status in real-time during development
   - Maintain quality standards with each task completion
   - Document progress through task updates

3. **Quality Assurance Phase**
   - Run quality checks after each task completion
   - Update task status only after quality validation
   - Use TaskMaster complexity analysis for risk assessment
   - Monitor project health through TaskMaster metrics

4. **Integration Phase**
   - Complete integration tasks using TaskMaster coordination
   - Validate end-to-end functionality
   - Update final task statuses
   - Generate project completion reports

### Quality Standards Integration

**🚨 CRITICAL: ZERO-TOLERANCE QUALITY POLICY**

**ABSOLUTE REQUIREMENTS - NO EXCEPTIONS:**

### 🛑 **STOP-GATE QUALITY CHECKS**
**BEFORE PROCEEDING TO NEXT TASK OR COMMIT:**

1. **MANDATORY Unit tests**: 100% pass rate - **ZERO FAILURES ALLOWED**
2. **MANDATORY Critical lint checks**: **ZERO F,E9 violations ALLOWED**
3. **MANDATORY Pre-commit validation**: **MUST PASS ALL HOOKS**
4. **MANDATORY CI Status**: **ALL CHECKS MUST BE GREEN**
5. **MANDATORY TaskMaster update**: Update status ONLY after quality validation

**⚠️ QUALITY FAILURE PROTOCOL:**
- **IF ANY CHECK FAILS**: STOP all development immediately
- **INVESTIGATE ROOT CAUSE**: Never proceed with "quick fixes"
- **FIX SYSTEMATICALLY**: Address underlying issues, not symptoms
- **RE-RUN ALL CHECKS**: Verify complete resolution before proceeding
- **ESCALATE IF STUCK**: Ask for help rather than compromising quality

### 🔍 **MANDATORY QUALITY SEQUENCE**
**Execute in EXACT order after each task:**

```bash
# STEP 1: Core Quality Validation (MUST PASS)
hatch -e dev run pytest                    # All tests pass
hatch -e dev run ruff check --select=F,E9 # Zero critical violations

# STEP 2: Comprehensive Quality Validation (MUST PASS)
hatch -e dev run pre-commit run --all-files # All hooks pass

# STEP 3: Git Status Verification (MUST BE CLEAN)
git status                                 # Clean working tree

# STEP 4: CI Validation (IF APPLICABLE)
gh pr checks                              # All CI checks passing
```

**🚨 CONTAMINATION PREVENTION:**
- **FILE INTEGRITY**: Verify no unrelated files in project
- **DEPENDENCY INTEGRITY**: Check no foreign dependencies introduced
- **TEST ISOLATION**: Ensure tests don't interfere with each other
- **ASYNC CLEANUP**: Verify no hanging tasks or resources

## Git Workflow Integration

### Branch Strategy
- **Main development branch**: `feature/project-name` or `main`
- **Task branches**: `feature/task-X-description` (for complex tasks)
- **Quality branches**: `quality/fixes-batch-X` (for quality improvements)

### Commit Strategy
Each task completion gets a commit following this pattern:
```
feat: implement Task X - [Task Title]

- [Key implementation detail 1]
- [Key implementation detail 2]
- [Integration points or dependencies resolved]

✅ Quality: [Quality check results]
✅ Tests: [Test status]
📋 TaskMaster: [Task status update]
🎯 Next: [Next task or dependency]

🤖 Generated with [Claude Code](https://claude.ai/code)
Co-Authored-By: Claude <noreply@anthropic.com>
```

## PR Management Best Practices

**🚨 IMPORTANT: UPDATE PR DESCRIPTION, NOT COMMENTS**

- **DO**: Use `gh pr edit <PR_NUMBER> --body` to update PR summary with TaskMaster progress
- **DON'T**: Post individual comments for each task (clutters discussion)
- **Reason**: PR description serves as authoritative progress summary

**PR Description Template**:
```markdown
# [Project Title] - [Current Phase]

## Progress Summary
- **X/Y tasks completed** ✅
- **Current Phase:** [Phase description from TaskMaster]
- **Quality Status:** [Test count] passing, zero critical violations

## Recent Milestones (from TaskMaster)
- ✅ Task X: [Description] - [Key achievement]
- ✅ Task Y: [Description] - [Key achievement]

## Next Steps (from TaskMaster)
- [Next prioritized tasks from taskmaster-ai__next_task]

## Quality Verification
- All CI checks passing
- TaskMaster project health: [status]
```

## Development Tools Integration

### Primary Development Tools
- **Task Management**: `taskmaster-ai` MCP tool (primary)
- **Code Implementation**: `aider` or other AI coding tools
- **Problem Analysis**: `sequentialthinking` for complex decisions
- **Alternative Solutions**: Additional AI models for consultation
- **Quality Assurance**: Project-specific linting and testing tools

### TaskMaster AI Commands Reference

**Core Task Management**:
- `get_tasks()` - View all tasks and current status
- `get_task(id="X")` - Get detailed task information
- `next_task()` - Get next prioritized task to work on
- `set_task_status(id="X", status="done")` - Update task completion

**Advanced Features**:
- `analyze_project_complexity()` - Assess project complexity
- `expand_task(id="X")` - Break complex tasks into subtasks
- `add_dependency(id="X", dependsOn="Y")` - Manage task dependencies
- `complexity_report()` - Generate complexity analysis

## Context Restart Instructions

**🚨 MANDATORY STARTUP SEQUENCE - NEVER SKIP:**

When context window requires restart:

1. **Read this framework document** for workflow guidelines
2. **MANDATORY**: Run complete quality validation sequence:
   ```bash
   hatch -e dev run pytest                    # Verify all tests pass
   hatch -e dev run ruff check --select=F,E9 # Verify zero critical violations
   hatch -e dev run pre-commit run --all-files # Verify all hooks pass
   git status                                 # Verify clean working tree
   ```
3. **Check TaskMaster status**: `mcp__taskmaster-ai__get_tasks()`
4. **Identify current focus**: `mcp__taskmaster-ai__next_task()`
5. **Review project health**: `mcp__taskmaster-ai__complexity_report()`
6. **Check git status**: `git log --oneline -5` and `git status`
7. **Verify CI status**: `gh pr checks` (if applicable)
8. **CONTAMINATION SCAN**: Verify no unrelated files in project structure
9. **Continue systematic development** following TaskMaster priorities

**⚠️ IF ANY STARTUP CHECK FAILS:**
- **STOP immediately** - do not proceed with development
- **Investigate root cause** thoroughly
- **Fix systematically** before resuming work
- **Document findings** for future prevention

## Framework Customization

### Project-Specific Adaptations

1. **Quality Commands**: Update quality check commands for your tech stack
2. **Task Complexity**: Adjust task breakdown complexity based on project size
3. **Branch Strategy**: Adapt branch naming to your team's conventions
4. **CI/CD Integration**: Configure TaskMaster updates to trigger on CI events

### Technology Stack Examples

**Python Projects**:
```bash
# Quality checks
hatch -e dev run pytest
hatch -e dev run ruff check --select=F,E9
hatch -e dev run mypy src/

# Dependencies
pip install taskmaster-ai  # If available as package
```

**Node.js Projects**:
```bash
# Quality checks
npm test
npm run lint
npm run type-check
npm run build

# Task management via MCP
# Use taskmaster-ai MCP server
```

**Go Projects**:
```bash
# Quality checks
go test ./...
go vet ./...
golangci-lint run
go build ./...
```

## Important Framework Principles

### 🚨 **FRAMEWORK FUNDAMENTALS**

- **TaskMaster-Driven**: All project tracking through TaskMaster AI, not manual files
- **Quality-First**: Never proceed without passing quality checks
- **Systematic Progress**: Follow task dependencies and priorities
- **Real-Time Updates**: Update TaskMaster status as work progresses
- **Documentation Through Tools**: Let TaskMaster generate reports instead of manual docs

### ⚠️ **CRITICAL SUCCESS FACTORS**

- **Use TaskMaster AI** instead of manual tracking documents
- **Maintain task dependency integrity** for systematic progress
- **Update task status immediately** after completion
- **Run quality checks before** marking tasks complete
- **Follow git workflow** with meaningful commit messages linked to tasks
- **Keep PR descriptions current** with TaskMaster progress updates

### 🛡️ **DISASTER PREVENTION PROTOCOLS**

**EARLY WARNING SYSTEMS:**
- **CI Failure**: Immediate investigation required - never ignore
- **Test Degradation**: Any reduction in test coverage triggers review
- **Lint Violations**: Address immediately before they multiply
- **Dependency Drift**: Monitor for unexpected package changes

**RECOVERY PROCEDURES:**
- **Project Corruption**: Stop immediately, identify source, clean systematically
- **CI Breakage**: Isolate changes, test locally, fix root cause
- **Quality Regression**: Rollback to last known good state if needed
- **Task Pile-up**: Re-prioritize with TaskMaster, break down complex tasks

**QUALITY ESCALATION MATRIX:**
1. **Green**: All checks pass → Proceed normally
2. **Yellow**: Non-critical warnings → Address within current task
3. **Red**: Critical failures → STOP, investigate, fix before proceeding
4. **Black**: Project corruption → Emergency cleanup protocol

**🎯 This framework transforms chaotic development into systematic, trackable, and high-quality project delivery using AI-assisted project management tools.**

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
