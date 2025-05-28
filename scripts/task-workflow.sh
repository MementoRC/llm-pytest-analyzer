#!/bin/bash
# TaskMaster AI Development Workflow Script
# Based on Environment Manager Integration Project (Tasks 1-10)
# Usage: ./scripts/task-workflow.sh [task_id] [phase]

set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_ID="${1:-}"
PHASE="${2:-all}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if we're in the right directory
if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
    log_error "Must be run from project root directory"
    exit 1
fi

# Phase 1: Task Status and Planning
phase_1_planning() {
    log_info "Phase 1: Task Status and Planning"

    echo "TaskMaster Commands to run in Claude Code:"
    echo "mcp__taskmaster-ai__get_tasks(projectRoot=\"$PROJECT_ROOT\", withSubtasks=true)"
    echo "mcp__taskmaster-ai__next_task(projectRoot=\"$PROJECT_ROOT\")"

    if [[ -n "$TASK_ID" ]]; then
        echo "mcp__taskmaster-ai__set_task_status(id=\"$TASK_ID\", status=\"in-progress\", projectRoot=\"$PROJECT_ROOT\")"
        echo "TodoWrite([{\"content\": \"Implement Task $TASK_ID - [Description]\", \"status\": \"in_progress\", \"priority\": \"medium\", \"id\": \"task-$TASK_ID\"}])"
    fi

    log_success "Phase 1 complete - TaskMaster status checked"
}

# Phase 4: Quality Validation Sequence
phase_4_quality() {
    log_info "Phase 4: Quality Validation Sequence (MANDATORY)"

    # Detect environment manager (order matters!)
    if [[ -f "pixi.toml" ]] || ([[ -f "pyproject.toml" ]] && grep -q "tool.pixi" pyproject.toml); then
        ENV_CMD="pixi run -e dev"
    elif [[ -f "pyproject.toml" ]] && grep -q "tool.poetry" pyproject.toml; then
        ENV_CMD="poetry run"
    elif [[ -f "pyproject.toml" ]] && grep -q "tool.hatch" pyproject.toml; then
        ENV_CMD="hatch run test:"
    else
        ENV_CMD=""
        log_warning "No environment manager detected, using direct commands"
    fi

    log_info "Using environment command: ${ENV_CMD:-direct}"

    # Run quality checks in order
    echo "🚨 MANDATORY QUALITY SEQUENCE:"

    if [[ -n "$TASK_ID" ]]; then
        log_info "11. Running tests for task $TASK_ID..."
        if [[ -f "tests/*/test_*$TASK_ID*.py" ]] || [[ -f "tests/test_*$TASK_ID*.py" ]]; then
            $ENV_CMD pytest tests/**/test_*$TASK_ID*.py -v || {
                log_error "Task-specific tests failed!"
                exit 1
            }
        fi
    fi

    log_info "12. Running full test suite..."
    $ENV_CMD pytest -x || {
        log_error "Full test suite failed!"
        exit 1
    }

    log_info "13. Checking critical lint violations..."
    $ENV_CMD ruff check --select=F,E9 || {
        log_error "Critical lint violations found!"
        exit 1
    }

    log_info "14. Running pre-commit hooks..."
    $ENV_CMD pre-commit run --all-files || {
        log_warning "Pre-commit hooks found issues (may have auto-fixed)"
    }

    log_info "15. Verifying git status..."
    if [[ -n "$(git status --porcelain)" ]]; then
        log_warning "Git working directory is not clean:"
        git status --short
    else
        log_success "Git working directory is clean"
    fi

    log_success "Phase 4 complete - All quality checks passed!"
}

# Phase 5: Task Completion and Git Workflow
phase_5_completion() {
    log_info "Phase 5: Task Completion and Git Workflow"

    if [[ -z "$TASK_ID" ]]; then
        log_error "Task ID required for completion phase"
        exit 1
    fi

    echo "TaskMaster Commands to run in Claude Code:"
    echo "mcp__taskmaster-ai__set_task_status(id=\"$TASK_ID\", status=\"done\", projectRoot=\"$PROJECT_ROOT\")"
    echo "TodoWrite([{\"content\": \"Implement Task $TASK_ID - [Description]\", \"status\": \"completed\", \"priority\": \"medium\", \"id\": \"task-$TASK_ID\"}])"

    log_info "Git workflow commands (run manually):"
    echo "git add [relevant files]  # Be selective, avoid git add ."
    echo "git commit -m \"feat: implement Task $TASK_ID - [Task Title]"
    echo ""
    echo "- [Key implementation detail 1]"
    echo "- [Key implementation detail 2]"
    echo ""
    echo "✅ Quality: XXX tests passing, zero critical violations"
    echo "✅ Tests: Complete test suite with [key test coverage]"
    echo "📋 TaskMaster: Task $TASK_ID marked complete"
    echo "🎯 Next: Task Y - [Next Task Description]"
    echo ""
    echo "🤖 Generated with [Claude Code](https://claude.ai/code)"
    echo ""
    echo "Co-Authored-By: Claude <noreply@anthropic.com>\""
    echo ""
    echo "git push origin [branch-name]"

    log_success "Phase 5 complete - Ready for git workflow"
}

# Quick quality check function
quick_quality() {
    log_info "Running quick quality validation..."

    # Detect environment manager (order matters!)
    if [[ -f "pixi.toml" ]] || ([[ -f "pyproject.toml" ]] && grep -q "tool.pixi" pyproject.toml); then
        ENV_CMD="pixi run -e dev"
    elif [[ -f "pyproject.toml" ]] && grep -q "tool.poetry" pyproject.toml; then
        ENV_CMD="poetry run"
    elif [[ -f "pyproject.toml" ]] && grep -q "tool.hatch" pyproject.toml; then
        ENV_CMD="hatch run test:"
    else
        ENV_CMD=""
    fi

    echo "Testing: $ENV_CMD pytest -x"
    echo "Linting: $ENV_CMD ruff check --select=F,E9"
    echo "Pre-commit: $ENV_CMD pre-commit run --all-files"
    echo "Git status: git status"

    # Actually run the checks
    log_info "Running tests..."
    $ENV_CMD pytest -x

    log_info "Running lint checks..."
    $ENV_CMD ruff check --select=F,E9

    log_info "Running pre-commit..."
    $ENV_CMD pre-commit run --all-files

    log_info "Checking git status..."
    git status

    log_success "Quick quality check complete!"
}

# Display usage information
usage() {
    echo "TaskMaster AI Development Workflow Script"
    echo ""
    echo "Usage: $0 [task_id] [phase]"
    echo ""
    echo "Phases:"
    echo "  all         - Show all phases (default)"
    echo "  planning    - Phase 1: Task Status and Planning"
    echo "  quality     - Phase 4: Quality Validation Sequence"
    echo "  completion  - Phase 5: Task Completion and Git Workflow"
    echo "  check       - Quick quality validation"
    echo ""
    echo "Examples:"
    echo "  $0 8 quality      # Run quality checks for task 8"
    echo "  $0 9 completion   # Show completion workflow for task 9"
    echo "  $0 - check        # Quick quality check"
    echo ""
    echo "Environment Managers Supported:"
    echo "  - Pixi (pixi.toml)"
    echo "  - Poetry (pyproject.toml with [tool.poetry])"
    echo "  - Hatch (pyproject.toml with [tool.hatch])"
    echo "  - Direct commands (fallback)"
}

# Main script logic
main() {
    case "$PHASE" in
        "planning")
            phase_1_planning
            ;;
        "quality")
            phase_4_quality
            ;;
        "completion")
            phase_5_completion
            ;;
        "check")
            quick_quality
            ;;
        "all"|"")
            echo "=== TaskMaster AI Development Workflow ==="
            echo ""
            phase_1_planning
            echo ""
            echo "Phase 2: Implementation Analysis - Use Claude Code tools:"
            echo "  Glob(pattern=\"**/*[relevant_pattern]*\")"
            echo "  Grep(pattern=\"[relevant_concept]\", include=\"*.py\")"
            echo "  Read(file_path=\"/path/to/key/file.py\")"
            echo "  Task(description=\"Search patterns\", prompt=\"Find related implementations\")"
            echo ""
            echo "Phase 3: Core Implementation - Use Claude Code tools:"
            echo "  Write(file_path=\"/path/to/new/module.py\", content=\"[implementation]\")"
            echo "  Write(file_path=\"/path/to/test_module.py\", content=\"[tests]\")"
            echo "  Edit(file_path=\"/path/to/__init__.py\", old_string=\"\", new_string=\"\")"
            echo ""
            phase_4_quality
            echo ""
            phase_5_completion
            echo ""
            echo "Phase 6: PR Management - Use Claude Code tools:"
            echo "  gh pr checks"
            echo "  gh pr edit [PR_NUMBER] --body \"[updated description]\""
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

# Run main function
main
