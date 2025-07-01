import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to PYTHONPATH to allow imports from pytest_analyzer
# This is crucial for the script to find the core modules when run from the project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService
from pytest_analyzer.core.factory import create_analyzer_service
from pytest_analyzer.core.models.pytest_failure import FixSuggestion
from pytest_analyzer.utils.settings import Settings, load_settings

# Configure logging for the script
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("run_analyzer_script")


def setup_parser() -> argparse.ArgumentParser:
    """Set up the command-line argument parser for the helper script."""
    parser = argparse.ArgumentParser(
        description="Helper script for pytest-analyzer in CI workflows."
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", required=True
    )

    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze pytest failures from a report file."
    )
    analyze_parser.add_argument(
        "--report-file",
        type=str,
        required=True,
        help="Path to the pytest JSON report file.",
    )
    analyze_parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.8,
        help="Minimum confidence for a fix suggestion to be considered.",
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    apply_parser = subparsers.add_parser(
        "apply", help="Apply a specific fix suggestion."
    )
    apply_parser.add_argument(
        "--suggestion-id",
        type=str,
        required=True,
        help="ID of the fix suggestion to apply.",
    )
    apply_parser.add_argument(
        "--target-file",
        type=str,
        required=True,
        help="Path to the file where the fix should be applied.",
    )
    apply_parser.set_defaults(func=cmd_apply)

    return parser


def get_analyzer_service(
    settings: Optional[Settings] = None,
) -> DIPytestAnalyzerService:
    """
    Initializes and returns the PytestAnalyzerService.
    Sets up default settings suitable for CI environment.
    """
    if settings is None:
        settings = load_settings()
    # Force LLM usage and set a reasonable timeout for CI
    settings.use_llm = True
    settings.llm_timeout = 120
    # Ensure project_root is set, defaulting to current working directory
    if not settings.project_root:
        settings.project_root = Path.cwd()
    return create_analyzer_service(settings=settings)


def cmd_analyze(args: argparse.Namespace) -> None:
    """
    Command handler for 'analyze'.
    Analyzes a pytest JSON report and outputs the best suggestion as JSON.
    """
    report_file_path = Path(args.report_file)
    if not report_file_path.exists():
        logger.error(f"Report file not found: {report_file_path}")
        json.dump(
            {
                "success": False,
                "message": f"Report file not found: {report_file_path}",
                "has_high_confidence_fix": False,
            },
            sys.stdout,
            indent=2,
        )
        sys.exit(1)

    try:
        analyzer_service = get_analyzer_service()
        # The analyze_pytest_output method is expected to return a list of FixSuggestion objects
        suggestions: List[FixSuggestion] = analyzer_service.analyze_pytest_output(
            str(report_file_path)
        )

        best_suggestion: Optional[FixSuggestion] = None
        if suggestions:
            # Filter for suggestions meeting the minimum confidence threshold
            filtered_suggestions = [
                s
                for s in suggestions
                if s.confidence.numeric_value >= args.min_confidence
            ]
            if filtered_suggestions:
                # If multiple high-confidence suggestions, pick the highest
                best_suggestion = max(
                    filtered_suggestions, key=lambda s: s.confidence.numeric_value
                )
            elif suggestions:
                # If no high-confidence suggestions, still report the highest confidence one found
                # but mark it as not high-confidence.
                best_suggestion = max(
                    suggestions, key=lambda s: s.confidence.numeric_value
                )
                logger.info(
                    f"Highest confidence suggestion ({best_suggestion.confidence.numeric_value:.2f}) "
                    f"is below minimum threshold ({args.min_confidence:.2f})."
                )

        output_data: Dict[str, Any] = {
            "success": True,
            "has_high_confidence_fix": False,
            "suggestion_id": "",
            "target_file": "",
            "confidence_score": 0.0,
            "explanation": "",
            "message": "No high confidence fix found or no failures analyzed.",
        }

        if best_suggestion:
            output_data["suggestion_id"] = str(best_suggestion.id)
            # The target_file should ideally come from the suggestion's metadata or a dedicated field
            # For now, we assume it's in metadata or fallback to a common name.
            output_data["target_file"] = str(
                best_suggestion.metadata.get("target_file", "")
                or (
                    best_suggestion.code_changes.keys().__iter__().__next__()
                    if best_suggestion.code_changes
                    else ""
                )
            )
            output_data["confidence_score"] = best_suggestion.confidence.numeric_value
            output_data["explanation"] = best_suggestion.explanation
            output_data["message"] = "Analysis complete."

            if best_suggestion.confidence.numeric_value >= args.min_confidence:
                output_data["has_high_confidence_fix"] = True
                output_data["message"] = "High confidence fix found."

        json.dump(output_data, sys.stdout, indent=2)
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        json.dump(
            {
                "success": False,
                "message": f"Error during analysis: {str(e)}",
                "has_high_confidence_fix": False,
            },
            sys.stdout,
            indent=2,
        )
        sys.exit(1)


def cmd_apply(args: argparse.Namespace) -> None:
    """
    Command handler for 'apply'.
    Applies a specific fix suggestion by ID to a target file and outputs the result as JSON.
    """
    suggestion_id = args.suggestion_id
    target_file = Path(args.target_file)

    if not target_file.exists():
        logger.error(f"Target file not found for applying fix: {target_file}")
        json.dump(
            {
                "success": False,
                "message": f"Target file not found: {target_file}",
                "diff_preview": "",
            },
            sys.stdout,
            indent=2,
        )
        sys.exit(1)

    try:
        analyzer_service = get_analyzer_service()
        # The apply_suggestion_by_id method is expected to apply the fix
        # and return a dictionary with success status, message, and diff_preview.
        # This method needs to be implemented in DIPytestAnalyzerService or its facade
        # to retrieve the FixSuggestion object by ID from its internal cache/storage.
        result = analyzer_service.apply_suggestion_by_id(
            suggestion_id=suggestion_id, target_file=str(target_file)
        )

        json.dump(result, sys.stdout, indent=2)
        sys.exit(0 if result.get("success", False) else 1)

    except Exception as e:
        logger.error(f"Error during fix application: {e}", exc_info=True)
        json.dump(
            {
                "success": False,
                "message": f"Error during fix application: {str(e)}",
                "diff_preview": "",
            },
            sys.stdout,
            indent=2,
        )
        sys.exit(1)


if __name__ == "__main__":
    parser = setup_parser()
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)
