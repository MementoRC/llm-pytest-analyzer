"""MCP Facade implementation for pytest-analyzer.

This module provides a facade that wraps the core PytestAnalyzerFacade to expose
MCP-compatible endpoints. It handles schema validation, error handling, and
transforms between MCP schemas and domain models.
"""

import functools
import logging
import time
from typing import Any, Callable, TypeVar

from pytest_analyzer.core.analyzer_facade import PytestAnalyzerFacade
from pytest_analyzer.core.errors import (
    AnalysisError,
    ExtractionError,
    LLMServiceError,
)

from .schemas import FixSuggestionData, MCPError, PytestFailureData
from .schemas.analyze_pytest_output import (
    AnalyzePytestOutputRequest,
    AnalyzePytestOutputResponse,
)
from .schemas.apply_suggestion import ApplySuggestionRequest, ApplySuggestionResponse
from .schemas.get_config import GetConfigRequest, GetConfigResponse
from .schemas.get_failure_summary import (
    GetFailureSummaryRequest,
    GetFailureSummaryResponse,
)
from .schemas.get_test_coverage import GetTestCoverageRequest, GetTestCoverageResponse
from .schemas.run_and_analyze import RunAndAnalyzeRequest, RunAndAnalyzeResponse
from .schemas.suggest_fixes import SuggestFixesRequest, SuggestFixesResponse
from .schemas.update_config import UpdateConfigRequest, UpdateConfigResponse
from .schemas.validate_suggestion import (
    ValidateSuggestionRequest,
    ValidateSuggestionResponse,
)

logger = logging.getLogger(__name__)

_R = TypeVar("_R")


def async_error_handler(operation_name: str):
    """Async error handler decorator for MCP facade methods."""

    def decorator(func: Callable[..., _R]) -> Callable[..., _R]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Error in {operation_name}: {e}")
                # Extract request from args to get request_id
                request = args[1] if len(args) > 1 else None
                request_id = getattr(request, "request_id", None)
                return MCPError(
                    code=f"{operation_name.upper()}_FAILED",
                    message=str(e),
                    request_id=request_id,
                )

        return wrapper

    return decorator


class MCPAnalyzerFacade:
    """
    MCP facade for pytest-analyzer that wraps the core analyzer facade.

    Provides MCP-compatible endpoints with schema validation, error handling,
    and transformation between MCP schemas and domain models.
    """

    def __init__(self, analyzer_facade: PytestAnalyzerFacade):
        """Initialize the MCP facade with a core analyzer facade instance."""
        self.analyzer = analyzer_facade

    def _measure_execution_time(func):
        """Decorator to measure execution time of MCP operations."""
        import functools

        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            result = await func(self, *args, **kwargs)
            execution_time = int(
                (time.time() - start_time) * 1000
            )  # Convert to milliseconds
            if hasattr(result, "execution_time_ms"):
                result.execution_time_ms = execution_time
            return result

        return wrapper

    def _transform_suggestion_to_mcp(self, suggestion: Any) -> FixSuggestionData:
        """Transform a FixSuggestion to MCP FixSuggestionData."""
        # Handle both domain entities and legacy models
        if hasattr(suggestion, "id") and hasattr(suggestion, "failure_id"):
            # New domain entity
            return FixSuggestionData(
                id=str(suggestion.id),
                failure_id=str(suggestion.failure_id),
                suggestion_text=suggestion.suggestion_text,
                code_changes=suggestion.code_changes,
                confidence_score=suggestion.confidence.numeric_value,
                explanation=suggestion.explanation,
                alternative_approaches=suggestion.alternative_approaches,
                file_path=suggestion.metadata.get("target_file", ""),
                line_number=suggestion.metadata.get("line_number", None),
            )
        else:
            # Legacy model from core.models.pytest_failure
            return FixSuggestionData(
                id=str(getattr(suggestion, "id", "unknown")),
                failure_id=str(getattr(suggestion.failure, "id", "unknown"))
                if hasattr(suggestion, "failure")
                else "unknown",
                suggestion_text=getattr(suggestion, "suggestion", ""),
                code_changes=getattr(suggestion, "code_changes", []),
                confidence_score=float(getattr(suggestion, "confidence", 0.0)),
                explanation=getattr(suggestion, "explanation", ""),
                alternative_approaches=[],
                file_path=getattr(suggestion.failure, "test_file", "")
                if hasattr(suggestion, "failure")
                else "",
                line_number=getattr(suggestion.failure, "line_number", None)
                if hasattr(suggestion, "failure")
                else None,
            )

    def _transform_failure_to_mcp(self, failure: Any) -> PytestFailureData:
        """Transform a PytestFailure to MCP PytestFailureData."""
        # Handle both domain entities and legacy models
        if hasattr(failure, "id") and hasattr(failure, "location"):
            # New domain entity
            return PytestFailureData(
                id=str(failure.id),
                test_name=failure.test_name,
                file_path=str(failure.location.file_path),
                failure_message=failure.failure_message,
                failure_type=failure.failure_type.name,
                line_number=failure.location.line_number,
                function_name=failure.location.function_name,
                class_name=failure.location.class_name,
                traceback=failure.traceback,
            )
        else:
            # Legacy model from core.models.pytest_failure
            return PytestFailureData(
                id=str(getattr(failure, "id", "unknown")),
                test_name=getattr(failure, "test_name", ""),
                file_path=getattr(failure, "test_file", ""),
                failure_message=getattr(failure, "error_message", ""),
                failure_type=getattr(failure, "error_type", ""),
                line_number=getattr(failure, "line_number", None),
                function_name="",  # Not available in legacy model
                class_name="",  # Not available in legacy model
                traceback=[getattr(failure, "traceback", "")]
                if getattr(failure, "traceback", "")
                else [],
            )

    async def analyze_pytest_output(
        self, request: AnalyzePytestOutputRequest
    ) -> AnalyzePytestOutputResponse:
        """Analyze pytest output file and generate fix suggestions."""
        start_time = time.time()

        # Validate request
        errors = request.validate()
        if errors:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return AnalyzePytestOutputResponse(
                success=False,
                request_id=request.request_id,
                failures=[],
                suggestions=[],
                parsing_errors=errors,
                execution_time_ms=execution_time_ms,
            )

        # Call core analyzer
        try:
            results = self.analyzer.analyze_pytest_output(request.file_path)
        except ExtractionError as e:
            logger.error(
                f"Extraction error in analyze_pytest_output: {e}",
                exc_info=True,
            )
            raise AnalysisError(
                f"Failed to analyze pytest output: {e}",
                context={"file_path": request.file_path},
                original_exception=e,
            ) from e

        # Transform results to MCP format
        suggestions = [self._transform_suggestion_to_mcp(s) for s in results]

        execution_time_ms = max(1, int((time.time() - start_time) * 1000))
        return AnalyzePytestOutputResponse(
            success=True,
            request_id=request.request_id,
            suggestions=suggestions,
            failures=[],  # Populated from analysis if available
            execution_time_ms=execution_time_ms,
        )

    async def run_and_analyze(
        self, request: RunAndAnalyzeRequest
    ) -> RunAndAnalyzeResponse:
        """Run pytest and analyze results in one operation."""
        start_time = time.time()

        errors = request.validate()
        if errors:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return RunAndAnalyzeResponse(
                success=False,
                request_id=request.request_id,
                warnings=errors,
                execution_time_ms=execution_time_ms,
            )

        try:
            results = self.analyzer.run_and_analyze(
                test_path=request.test_pattern,
                pytest_args=request.pytest_args,
                quiet=not request.capture_output,
            )
        except ExtractionError as e:
            logger.error(
                f"Extraction error in run_and_analyze: {e}",
                exc_info=True,
            )
            raise AnalysisError(
                f"Failed to run and analyze: {e}",
                context={"test_pattern": request.test_pattern},
                original_exception=e,
            ) from e

        suggestions = [self._transform_suggestion_to_mcp(s) for s in results]

        execution_time_ms = max(1, int((time.time() - start_time) * 1000))
        return RunAndAnalyzeResponse(
            success=True,
            request_id=request.request_id,
            suggestions=suggestions,
            pytest_success=len(results) == 0,
            tests_run=len(results),  # This should come from actual test counts
            execution_time_ms=execution_time_ms,
        )

    async def suggest_fixes(self, request: SuggestFixesRequest) -> SuggestFixesResponse:
        """Generate fix suggestions from raw pytest output."""
        start_time = time.time()

        errors = request.validate()
        if errors:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return SuggestFixesResponse(
                success=False,
                request_id=request.request_id,
                parsing_warnings=errors,
                execution_time_ms=execution_time_ms,
            )

        try:
            suggestions = self.analyzer.suggest_fixes(request.raw_output)
        except Exception as e:
            logger.error(
                f"LLM service error in suggest_fixes: {e}",
                exc_info=True,
            )
            raise LLMServiceError(
                f"Failed to suggest fixes: {e}",
                context={"raw_output": str(request.raw_output)[:100]},
                original_exception=e,
            ) from e

        mcp_suggestions = [self._transform_suggestion_to_mcp(s) for s in suggestions]

        execution_time_ms = max(1, int((time.time() - start_time) * 1000))
        return SuggestFixesResponse(
            success=True,
            request_id=request.request_id,
            suggestions=mcp_suggestions,
            confidence_score=sum(s.confidence_score for s in mcp_suggestions)
            / len(mcp_suggestions)
            if mcp_suggestions
            else 0.0,
            execution_time_ms=execution_time_ms,
        )

    async def apply_suggestion(
        self, request: ApplySuggestionRequest
    ) -> ApplySuggestionResponse:
        """
        Apply a fix suggestion to the target files, with backup, rollback, syntax validation, and optional Git integration.
        """
        import os
        import shutil
        import subprocess

        start_time = time.time()
        errors = request.validate()
        if errors:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return ApplySuggestionResponse(
                success=False,
                request_id=request.request_id,
                warnings=errors,
                execution_time_ms=execution_time_ms,
            )

        backup_path = None
        changes_applied = []
        syntax_valid = True
        syntax_errors = []
        rollback_available = False
        diff_preview = ""
        warnings = []
        git_branch_created = False
        git_commit_hash = None
        backup_created = False

        # 1. File permission validation (skip for dry run)
        target_file = request.target_file
        if not request.dry_run:
            if not os.path.isfile(target_file):
                execution_time_ms = max(1, int((time.time() - start_time) * 1000))
                return ApplySuggestionResponse(
                    success=False,
                    request_id=request.request_id,
                    suggestion_id=request.suggestion_id,
                    target_file=target_file,
                    warnings=[f"Target file does not exist: {target_file}"],
                    execution_time_ms=execution_time_ms,
                )
            if not os.access(target_file, os.W_OK):
                execution_time_ms = max(1, int((time.time() - start_time) * 1000))
                return ApplySuggestionResponse(
                    success=False,
                    request_id=request.request_id,
                    suggestion_id=request.suggestion_id,
                    target_file=target_file,
                    warnings=[
                        f"Insufficient permissions to write to file: {target_file}"
                    ],
                    execution_time_ms=execution_time_ms,
                )

        # Handle dry run - simulate success without file operations
        if request.dry_run:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return ApplySuggestionResponse(
                success=True,
                request_id=request.request_id,
                suggestion_id=request.suggestion_id,
                target_file=target_file,
                changes_applied=[target_file] if target_file else [],
                diff_preview="(dry run - no changes applied)",
                execution_time_ms=execution_time_ms,
            )

        # 2. Backup creation
        backup_path = target_file + request.backup_suffix
        try:
            shutil.copy2(target_file, backup_path)
            backup_created = True
        except Exception as e:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return ApplySuggestionResponse(
                success=False,
                request_id=request.request_id,
                suggestion_id=request.suggestion_id,
                target_file=target_file,
                warnings=[f"Failed to create backup: {str(e)}"],
                execution_time_ms=execution_time_ms,
            )

        # 3. Apply suggestion (core logic)
        try:
            # The core analyzer should apply the suggestion and return a result dict
            result = self.analyzer.apply_suggestion(
                request.suggestion_id,
                target_file=target_file,
                dry_run=request.dry_run,
            )
            if not result.get("success", False):
                raise Exception(
                    result.get("message", "Unknown error during apply_suggestion")
                )
            changes_applied = result.get("applied_files", [target_file])
            diff_preview = result.get("diff_preview", "")
        except Exception as e:
            logger.error(f"Error in apply_suggestion: {e}")
            # Rollback on error
            try:
                if backup_created:
                    shutil.copy2(backup_path, target_file)
                    rollback_available = True
            except Exception as rollback_err:
                warnings.append(f"Rollback failed: {str(rollback_err)}")
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return ApplySuggestionResponse(
                success=False,
                request_id=request.request_id,
                suggestion_id=request.suggestion_id,
                target_file=target_file,
                backup_path=backup_path if backup_created else None,
                changes_applied=[],
                rollback_available=rollback_available,
                warnings=[f"Failed to apply suggestion: {str(e)}"] + warnings,
                execution_time_ms=execution_time_ms,
            )

        # 4. Syntax validation
        if request.validate_syntax:
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    code = f.read()
                import ast

                try:
                    ast.parse(code, filename=target_file)
                    syntax_valid = True
                except SyntaxError as se:
                    syntax_valid = False
                    syntax_errors.append(f"{se.__class__.__name__}: {se}")
            except Exception as e:
                syntax_valid = False
                syntax_errors.append(f"Failed to read or parse file: {str(e)}")

        # 5. Git integration (optional, only if file is in a git repo)
        git_branch = request.metadata.get("git_branch") if request.metadata else None
        git_commit_message = (
            request.metadata.get(
                "git_commit_message", f"Apply suggestion {request.suggestion_id}"
            )
            if request.metadata
            else None
        )
        git_commit_hash = None
        if git_branch or git_commit_message:
            try:
                # Check if file is in a git repo
                repo_dir = None
                cur_dir = os.path.dirname(os.path.abspath(target_file))
                while (
                    cur_dir
                    and cur_dir != "/"
                    and not os.path.isdir(os.path.join(cur_dir, ".git"))
                ):
                    cur_dir = os.path.dirname(cur_dir)
                if os.path.isdir(os.path.join(cur_dir, ".git")):
                    repo_dir = cur_dir
                if repo_dir:
                    # Optionally create branch
                    if git_branch:
                        subprocess.run(
                            ["git", "checkout", "-b", git_branch],
                            cwd=repo_dir,
                            check=True,
                        )
                        git_branch_created = True
                    # Add and commit file
                    subprocess.run(
                        ["git", "add", target_file], cwd=repo_dir, check=True
                    )
                    commit_args = ["git", "commit", "-m", git_commit_message]
                    subprocess.run(commit_args, cwd=repo_dir, check=True)
                    # Get commit hash
                    res = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=repo_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    git_commit_hash = res.stdout.strip()
            except Exception as e:
                warnings.append(f"Git integration failed: {str(e)}")

        # 6. Rollback support (if syntax invalid, restore backup)
        if not syntax_valid and backup_created:
            try:
                shutil.copy2(backup_path, target_file)
                rollback_available = True
                warnings.append("Syntax validation failed, rolled back to backup.")
            except Exception as e:
                warnings.append(f"Rollback after syntax error failed: {str(e)}")

        execution_time_ms = max(1, int((time.time() - start_time) * 1000))
        return ApplySuggestionResponse(
            success=syntax_valid,
            request_id=request.request_id,
            suggestion_id=request.suggestion_id,
            target_file=target_file,
            backup_path=backup_path if backup_created else None,
            changes_applied=changes_applied,
            syntax_valid=syntax_valid,
            syntax_errors=syntax_errors,
            rollback_available=rollback_available,
            diff_preview=diff_preview,
            warnings=warnings,
            execution_time_ms=execution_time_ms,
            metadata={
                "git_branch_created": git_branch_created,
                "git_commit_hash": git_commit_hash,
            },
        )

    @async_error_handler("validate_suggestion")
    async def validate_suggestion(
        self, request: ValidateSuggestionRequest
    ) -> ValidateSuggestionResponse:
        """Validate a fix suggestion without applying changes."""
        start_time = time.time()

        errors = request.validate()
        if errors:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return ValidateSuggestionResponse(
                success=False,
                request_id=request.request_id,
                validation_errors=errors,
                execution_time_ms=execution_time_ms,
            )

        # This would need implementation in core analyzer
        # For now return a basic response
        execution_time_ms = max(1, int((time.time() - start_time) * 1000))
        return ValidateSuggestionResponse(
            success=True,
            request_id=request.request_id,
            suggestion_id=request.suggestion_id,
            target_file=request.target_file,
            is_valid=True,
            execution_time_ms=execution_time_ms,
        )

    @async_error_handler("get_failure_summary")
    async def get_failure_summary(
        self, request: GetFailureSummaryRequest
    ) -> GetFailureSummaryResponse:
        """Get failure statistics and categorization."""
        errors = request.validate()
        if errors:
            return GetFailureSummaryResponse(
                success=False, request_id=request.request_id, total_failures=0
            )

        # This would need implementation in core analyzer
        return GetFailureSummaryResponse(
            success=True,
            request_id=request.request_id,
            total_failures=0,
            failure_groups={},
        )

    @async_error_handler("get_test_coverage")
    async def get_test_coverage(
        self, request: GetTestCoverageRequest
    ) -> GetTestCoverageResponse:
        """Get test coverage information and reporting."""
        errors = request.validate()
        if errors:
            return GetTestCoverageResponse(success=False, request_id=request.request_id)

        # This would need implementation in core analyzer
        return GetTestCoverageResponse(
            success=True, request_id=request.request_id, percentage=0.0
        )

    @async_error_handler("get_config")
    async def get_config(self, request: GetConfigRequest) -> GetConfigResponse:
        """Get current analyzer configuration settings."""
        from pytest_analyzer.utils.settings import load_settings

        errors = request.validate()
        if errors:
            return GetConfigResponse(
                success=False, request_id=request.request_id, warnings=errors
            )

        # 1. Load settings
        try:
            settings = load_settings()
        except Exception as e:
            return GetConfigResponse(
                success=False,
                request_id=request.request_id,
                warnings=[f"Failed to load settings: {e}"],
            )

        # 2. Helper: flatten dataclass to dict, recursively, with descriptions
        def dataclass_to_dict(obj, section=None):
            from dataclasses import fields, is_dataclass

            result = {}
            for f in fields(obj):
                value = getattr(obj, f.name)
                # Hide sensitive fields
                if any(
                    kw in f.name.lower()
                    for kw in (
                        "key",
                        "token",
                        "password",
                        "secret",
                        "api_key",
                        "auth_token",
                    )
                ):
                    if value is not None:
                        value = "***"
                # Recursively flatten dataclasses
                if is_dataclass(value):
                    value = dataclass_to_dict(value)
                # Add description and allowed values if available
                entry = {"value": value}
                if f.metadata.get("description"):
                    entry["description"] = f.metadata["description"]
                # Add allowed values for enums or known fields
                if section == "llm" and f.name == "llm_provider":
                    entry["allowed_values"] = [
                        "anthropic",
                        "openai",
                        "azure",
                        "together",
                        "ollama",
                        "auto",
                    ]
                if section == "llm" and f.name == "llm_model":
                    entry["description"] = (
                        "Model to use (auto selects available models)"
                    )
                if section == "logging" and f.name == "log_level":
                    entry["allowed_values"] = [
                        "DEBUG",
                        "INFO",
                        "WARNING",
                        "ERROR",
                        "CRITICAL",
                    ]
                result[f.name] = entry
            return result

        # 3. Organize config by section
        config_data = {}

        # LLM section
        config_data["llm"] = {
            k: v
            for k, v in dataclass_to_dict(settings, section="llm").items()
            if k
            in [
                "use_llm",
                "llm_timeout",
                "llm_api_key",
                "llm_model",
                "llm_provider",
                "use_fallback",
                "auto_apply",
                "anthropic_api_key",
                "openai_api_key",
                "azure_api_key",
                "azure_endpoint",
                "azure_api_version",
                "together_api_key",
                "ollama_host",
                "ollama_port",
            ]
        }

        # MCP section
        config_data["mcp"] = dataclass_to_dict(settings.mcp)

        # Analysis section
        config_data["analysis"] = {
            k: v
            for k, v in dataclass_to_dict(settings, section="analysis").items()
            if k
            in [
                "max_suggestions",
                "max_suggestions_per_failure",
                "min_confidence",
                "parser_timeout",
                "analyzer_timeout",
                "max_failures",
                "preferred_format",
            ]
        }

        # Extraction section
        config_data["extraction"] = {
            k: v
            for k, v in dataclass_to_dict(settings, section="extraction").items()
            if k in ["pytest_timeout", "pytest_args"]
        }

        # Logging section
        config_data["logging"] = {
            k: v
            for k, v in dataclass_to_dict(settings, section="logging").items()
            if k in ["log_level", "debug"]
        }

        # Git section
        config_data["git"] = {
            k: v
            for k, v in dataclass_to_dict(settings, section="git").items()
            if k in ["check_git", "auto_init_git", "use_git_branches"]
        }

        # Remove sensitive values from all sections
        sensitive_keys = {"api_key", "token", "password", "auth_token", "secret"}
        for section in config_data:
            for k, v in config_data[section].items():
                if any(s in k.lower() for s in sensitive_keys):
                    v["value"] = "***" if v["value"] not in (None, "") else v["value"]

        # 4. Section filtering
        if request.section:
            filtered = {}
            if request.section in config_data:
                filtered[request.section] = config_data[request.section]
            else:
                return GetConfigResponse(
                    success=False,
                    request_id=request.request_id,
                    warnings=[f"Section '{request.section}' not found."],
                )
            config_data = filtered

        # 5. Include defaults if requested (already included)
        # 6. Exclude sensitive if requested (already done above)

        # 7. Compose response
        return GetConfigResponse(
            success=True,
            request_id=request.request_id,
            config_data=config_data,
            sections=list(config_data.keys()),
            defaults_included=True,
            sensitive_excluded=True,
        )

    @async_error_handler("update_config")
    async def update_config(self, request: UpdateConfigRequest) -> UpdateConfigResponse:
        """Update analyzer configuration settings."""
        import copy
        import os
        import shutil

        from pytest_analyzer.utils.settings import get_config_manager

        start_time = time.time()
        errors = request.validate()
        if errors:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return UpdateConfigResponse(
                success=False,
                request_id=request.request_id,
                validation_errors=errors,
                execution_time_ms=execution_time_ms,
            )

        manager = get_config_manager(force_reload=True)
        config_file_path = getattr(manager, "_config_file_path", None)
        backup_path = None
        backup_created = False
        warnings = []
        updated_fields = []
        applied_changes = {}
        validation_errors = []

        # 1. Create backup if requested and config file exists
        if (
            request.create_backup
            and config_file_path
            and os.path.isfile(config_file_path)
        ):
            backup_path = str(config_file_path) + ".bak"
            try:
                shutil.copy2(config_file_path, backup_path)
                backup_created = True
            except Exception as e:
                warnings.append(f"Failed to create backup: {e}")
                backup_path = None

        # 2. Load current config as dict
        current_settings = manager.get_settings()
        from dataclasses import asdict

        def deep_update(d, u, strategy="merge"):
            """Recursively update dict d with u using merge/replace/append."""
            for k, v in u.items():
                if (
                    isinstance(v, dict)
                    and isinstance(d.get(k), dict)
                    and strategy == "merge"
                ):
                    deep_update(d[k], v, strategy)
                elif (
                    isinstance(v, list)
                    and isinstance(d.get(k), list)
                    and strategy == "append"
                ):
                    d[k] = d[k] + v
                else:
                    d[k] = v
            return d

        config_dict = asdict(current_settings)
        original_config = copy.deepcopy(config_dict)

        # 3. Section filtering
        updates = request.config_updates
        if request.section:
            if request.section not in config_dict:
                validation_errors.append(
                    f"Section '{request.section}' not found in configuration."
                )
                execution_time_ms = max(1, int((time.time() - start_time) * 1000))
                return UpdateConfigResponse(
                    success=False,
                    request_id=request.request_id,
                    validation_errors=validation_errors,
                    execution_time_ms=execution_time_ms,
                )
            # Only update the specified section
            section_updates = updates.get(request.section, {})
            if not section_updates:
                validation_errors.append(
                    f"No updates provided for section '{request.section}'."
                )
                execution_time_ms = max(1, int((time.time() - start_time) * 1000))
                return UpdateConfigResponse(
                    success=False,
                    request_id=request.request_id,
                    validation_errors=validation_errors,
                    execution_time_ms=execution_time_ms,
                )
            updates = {request.section: section_updates}

        # 4. Merge/replace/append strategy
        merge_strategy = request.merge_strategy or "merge"
        new_config = copy.deepcopy(config_dict)
        try:
            if merge_strategy == "replace":
                for k, v in updates.items():
                    new_config[k] = v
            elif merge_strategy == "append":
                for k, v in updates.items():
                    if isinstance(new_config.get(k), list) and isinstance(v, list):
                        new_config[k] = new_config[k] + v
                    elif isinstance(new_config.get(k), dict) and isinstance(v, dict):
                        for subk, subv in v.items():
                            if isinstance(new_config[k].get(subk), list) and isinstance(
                                subv, list
                            ):
                                new_config[k][subk] = new_config[k][subk] + subv
                            else:
                                new_config[k][subk] = subv
                    else:
                        new_config[k] = v
            else:  # merge (default)
                deep_update(new_config, updates, strategy="merge")
        except Exception as e:
            validation_errors.append(f"Failed to apply updates: {e}")
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return UpdateConfigResponse(
                success=False,
                request_id=request.request_id,
                validation_errors=validation_errors,
                execution_time_ms=execution_time_ms,
            )

        # 5. Validate new config by trying to instantiate Settings
        from pytest_analyzer.utils.config_types import Settings

        try:
            Settings(**new_config)
        except Exception as e:
            validation_errors.append(f"Validation failed: {e}")
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return UpdateConfigResponse(
                success=False,
                request_id=request.request_id,
                validation_errors=validation_errors,
                execution_time_ms=execution_time_ms,
                backup_path=backup_path if backup_created else None,
            )

        # 6. If validate_only, do not write changes
        if request.validate_only:
            # Compute updated fields
            for k in updates:
                if config_dict.get(k) != new_config.get(k):
                    updated_fields.append(k)
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return UpdateConfigResponse(
                success=True,
                request_id=request.request_id,
                updated_fields=updated_fields,
                applied_changes=updates,
                validation_errors=[],
                execution_time_ms=execution_time_ms,
                backup_path=backup_path if backup_created else None,
                warnings=warnings,
                rollback_available=backup_created,
            )

        # 7. Write new config to file (YAML)
        import yaml

        if not config_file_path:
            # Create a default config file in the current working directory
            from pathlib import Path

            config_file_path = Path.cwd() / "pytest-analyzer.yaml"
            warnings.append(
                f"No config file found; creating new config file at {config_file_path}"
            )
            logger.info(f"Creating new configuration file at {config_file_path}")

            # Update the manager's config file path for future operations
            manager._config_file_path = config_file_path

        try:
            # Load existing config file or create empty dict if file doesn't exist
            file_config = {}
            if os.path.isfile(config_file_path):
                with open(config_file_path, "r") as f:
                    file_config = yaml.safe_load(f) or {}

            # Update with new values
            for k in updates:
                file_config[k] = new_config[k]

            # Write the updated config
            with open(config_file_path, "w") as f:
                yaml.safe_dump(
                    file_config, f, default_flow_style=False, sort_keys=False
                )
        except Exception as e:
            validation_errors.append(f"Failed to write config file: {e}")
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return UpdateConfigResponse(
                success=False,
                request_id=request.request_id,
                validation_errors=validation_errors,
                execution_time_ms=execution_time_ms,
                backup_path=backup_path if backup_created else None,
                warnings=warnings,
            )

        # 8. Reload config manager to pick up changes
        try:
            get_config_manager(force_reload=True)
        except Exception as e:
            warnings.append(f"Failed to reload configuration: {e}")

        # 9. Compute updated fields
        for k in updates:
            if original_config.get(k) != new_config.get(k):
                updated_fields.append(k)
                applied_changes[k] = new_config[k]

        execution_time_ms = max(1, int((time.time() - start_time) * 1000))
        return UpdateConfigResponse(
            success=True,
            request_id=request.request_id,
            updated_fields=updated_fields,
            applied_changes=applied_changes,
            execution_time_ms=execution_time_ms,
            backup_path=backup_path if backup_created else None,
            warnings=warnings,
            rollback_available=backup_created,
        )
