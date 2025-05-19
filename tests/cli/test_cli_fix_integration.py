#!/usr/bin/env python3
"""
End-to-end tests for the CLI fix application integration.

These tests verify that:
1. The CLI correctly handles --apply-fixes and --auto-apply flags
2. Interactive prompts work as expected
3. The entire flow from analysis to fix application works
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.pytest_analyzer.cli.analyzer_cli import (
    apply_suggestions_interactively,
    main,
)
from src.pytest_analyzer.core.analysis.fix_applier import FixApplicationResult
from src.pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure


class TestCLIFixIntegration:
    """Test suite for CLI fix application integration."""

    @pytest.fixture
    def mock_suggestions(self):
        """Create a list of mock suggestions for testing."""
        failure = PytestFailure(
            test_name="test_module::test_function",
            test_file="/path/to/test_file.py",
            error_type="AssertionError",
            error_message="assert 1 == 2",
            traceback="...",
            line_number=10,
            relevant_code="assert value == expected",
        )

        return [
            FixSuggestion(
                failure=failure,
                suggestion="Fix the assertion by correcting the expected value",
                confidence=0.9,
                code_changes={
                    "/path/to/source_file.py": "corrected code content",
                    "fingerprint": "abcdef123456",
                    "source": "llm",
                },
                explanation="The test expected 2 but the function returns 1",
            )
        ]

    def test_apply_fixes_flag(self):
        """Test that --apply-fixes flag enables interactive fix application."""
        # Mock argparse.ArgumentParser.parse_args to include --apply-fixes
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_args = MagicMock()
            mock_args.apply_fixes = True
            mock_args.auto_apply = False
            mock_args.test_path = "dummy_test.py"
            mock_args.output_file = None
            mock_args.verbosity = 1
            mock_args.quiet = False
            mock_args.debug = False
            mock_parse_args.return_value = mock_args

            # Mock analyzer service and apply_suggestions_interactively
            with (
                patch(
                    "src.pytest_analyzer.cli.analyzer_cli.PytestAnalyzerService"
                ) as mock_service_class,
                patch(
                    "src.pytest_analyzer.cli.analyzer_cli.apply_suggestions_interactively"
                ) as mock_apply,
            ):
                # Mock service to return suggestions
                mock_service = mock_service_class.return_value
                # Create proper FixSuggestion objects to return
                failure = PytestFailure(
                    test_name="test_module::test_function",
                    test_file="/path/to/test_file.py",
                    error_type="AssertionError",
                    error_message="assert 1 == 2",
                    traceback="...",
                    line_number=10,
                    relevant_code="assert value == expected",
                )
                suggestions = [
                    FixSuggestion(
                        failure=failure,
                        suggestion="Fix the assertion",
                        confidence=0.9,
                        code_changes={
                            "/path/to/source_file.py": "corrected code content",
                            "fingerprint": "abcdef123456",
                            "source": "llm",
                        },
                        explanation="Fix explanation",
                    )
                ]
                mock_service.run_and_analyze.return_value = suggestions

                # Run CLI main
                main()

                # Check that apply_suggestions_interactively was called
                mock_apply.assert_called_once()
                # Verify that the first argument is our suggestions list
                assert mock_apply.call_args[0][0] == suggestions, (
                    "Should pass suggestions to apply_suggestions_interactively"
                )

    def test_auto_apply_flag(self):
        """Test that --auto-apply flag enables automatic fix application."""
        # Mock argparse.ArgumentParser.parse_args to include --auto-apply
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_args = MagicMock()
            mock_args.apply_fixes = False
            mock_args.auto_apply = True
            mock_args.test_path = "dummy_test.py"
            mock_args.output_file = None
            mock_args.verbosity = 1
            mock_args.quiet = False
            mock_args.debug = False
            mock_parse_args.return_value = mock_args

            # Mock analyzer service and apply_suggestions_interactively
            with (
                patch(
                    "src.pytest_analyzer.cli.analyzer_cli.PytestAnalyzerService"
                ) as mock_service_class,
                patch(
                    "src.pytest_analyzer.cli.analyzer_cli.apply_suggestions_interactively"
                ) as mock_apply,
            ):
                # Mock service to return suggestions
                mock_service = mock_service_class.return_value
                # Create proper FixSuggestion objects to return
                failure = PytestFailure(
                    test_name="test_module::test_function",
                    test_file="/path/to/test_file.py",
                    error_type="AssertionError",
                    error_message="assert 1 == 2",
                    traceback="...",
                    line_number=10,
                    relevant_code="assert value == expected",
                )
                suggestions = [
                    FixSuggestion(
                        failure=failure,
                        suggestion="Fix the assertion",
                        confidence=0.9,
                        code_changes={
                            "/path/to/source_file.py": "corrected code content",
                            "fingerprint": "abcdef123456",
                            "source": "llm",
                        },
                        explanation="Fix explanation",
                    )
                ]
                mock_service.run_and_analyze.return_value = suggestions

                # Run CLI main
                main()

                # Check that apply_suggestions_interactively was called
                mock_apply.assert_called_once()
                # Verify that the first argument is our suggestions list
                assert mock_apply.call_args[0][0] == suggestions, (
                    "Should pass suggestions to apply_suggestions_interactively"
                )
                # Verify that the args parameter has auto_apply=True
                assert mock_apply.call_args[0][2].auto_apply, (
                    "Should pass args with auto_apply=True"
                )

    def test_no_apply_flags(self):
        """Test that without --apply-fixes or --auto-apply, fixes are not applied."""
        # Mock argparse.ArgumentParser.parse_args with no apply flags
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_args = MagicMock()
            mock_args.apply_fixes = False
            mock_args.auto_apply = False
            mock_args.test_path = "dummy_test.py"
            mock_args.output_file = None
            mock_args.verbosity = 1
            mock_args.quiet = False
            mock_args.debug = False
            mock_parse_args.return_value = mock_args

            # Mock analyzer service and apply_suggestions_interactively
            with (
                patch(
                    "src.pytest_analyzer.cli.analyzer_cli.PytestAnalyzerService"
                ) as mock_service_class,
                patch(
                    "src.pytest_analyzer.cli.analyzer_cli.apply_suggestions_interactively"
                ) as mock_apply,
            ):
                # Mock service to return suggestions
                mock_service = mock_service_class.return_value
                # Create proper FixSuggestion objects to return
                failure = PytestFailure(
                    test_name="test_module::test_function",
                    test_file="/path/to/test_file.py",
                    error_type="AssertionError",
                    error_message="assert 1 == 2",
                    traceback="...",
                    line_number=10,
                    relevant_code="assert value == expected",
                )
                suggestions = [
                    FixSuggestion(
                        failure=failure,
                        suggestion="Fix the assertion",
                        confidence=0.9,
                        code_changes={
                            "/path/to/source_file.py": "corrected code content",
                            "fingerprint": "abcdef123456",
                            "source": "llm",
                        },
                        explanation="Fix explanation",
                    )
                ]
                mock_service.run_and_analyze.return_value = suggestions

                # Run CLI main
                main()

                # Check that apply_suggestions_interactively was NOT called
                mock_apply.assert_not_called()

    def test_interactive_apply_yes(self, mock_suggestions, capsys):
        """Test interactive application with 'y' input."""
        # Mock the analyzer service and fix applier
        mock_service = MagicMock()
        mock_service.apply_suggestion.return_value = FixApplicationResult(
            success=True,
            message="Fix applied successfully",
            applied_files=[Path("/path/to/source_file.py")],
            rolled_back_files=[],
        )

        # Mock user input to choose 'y'
        with patch("builtins.input", return_value="y"):
            # Run interactive apply
            apply_suggestions_interactively(
                mock_suggestions, mock_service, MagicMock(auto_apply=False)
            )

            # Check that apply_suggestion was called
            mock_service.apply_suggestion.assert_called_once_with(mock_suggestions[0])

            # Check output
            captured = capsys.readouterr()
            assert "Applying fix..." in captured.out
            assert "Success" in captured.out

    def test_interactive_apply_no(self, mock_suggestions, capsys):
        """Test interactive application with 'n' input."""
        # Mock the analyzer service
        mock_service = MagicMock()

        # Mock user input to choose 'n'
        with patch("builtins.input", return_value="n"):
            # Run interactive apply
            apply_suggestions_interactively(
                mock_suggestions, mock_service, MagicMock(auto_apply=False)
            )

            # Check that apply_suggestion was NOT called
            mock_service.apply_suggestion.assert_not_called()

            # Check output
            captured = capsys.readouterr()
            assert "Skipping this suggestion" in captured.out

    def test_interactive_apply_diff(self, mock_suggestions, capsys):
        """Test interactive application with 'd' then 'y' input."""
        # Mock the analyzer service
        mock_service = MagicMock()
        mock_service.apply_suggestion.return_value = FixApplicationResult(
            success=True,
            message="Fix applied successfully",
            applied_files=[Path("/path/to/source_file.py")],
            rolled_back_files=[],
        )

        # Mock show_file_diff to avoid file access
        with (
            patch(
                "src.pytest_analyzer.cli.analyzer_cli.show_file_diff", return_value=True
            ),
            patch("builtins.input", side_effect=["d", "y"]),
        ):
            # Run interactive apply
            apply_suggestions_interactively(
                mock_suggestions, mock_service, MagicMock(auto_apply=False)
            )

            # Check that apply_suggestion was called
            mock_service.apply_suggestion.assert_called_once_with(mock_suggestions[0])

            # Check output
            captured = capsys.readouterr()
            assert "Applying fix..." in captured.out
            assert "Success" in captured.out

    def test_interactive_apply_quit(self, mock_suggestions, capsys):
        """Test interactive application with 'q' input."""
        # Mock the analyzer service
        mock_service = MagicMock()

        # Mock user input to choose 'q'
        with patch("builtins.input", return_value="q"):
            # Run interactive apply
            apply_suggestions_interactively(
                mock_suggestions, mock_service, MagicMock(auto_apply=False)
            )

            # Check that apply_suggestion was NOT called
            mock_service.apply_suggestion.assert_not_called()

            # Check output
            captured = capsys.readouterr()
            assert "Quitting fix application" in captured.out

    def test_auto_apply_confirmation(self, mock_suggestions, capsys):
        """Test auto-apply with confirmation."""
        # Mock the analyzer service
        mock_service = MagicMock()
        mock_service.apply_suggestion.return_value = FixApplicationResult(
            success=True,
            message="Fix applied successfully",
            applied_files=[Path("/path/to/source_file.py")],
            rolled_back_files=[],
        )

        # Mock user input to confirm auto-apply
        with patch("builtins.input", return_value="y"):
            # Run interactive apply with auto_apply=True
            apply_suggestions_interactively(
                mock_suggestions, mock_service, MagicMock(auto_apply=True)
            )

            # Check that apply_suggestion was called
            mock_service.apply_suggestion.assert_called_once_with(mock_suggestions[0])

            # Check output
            captured = capsys.readouterr()
            assert "AUTO-APPLY MODE ENABLED" in captured.out
            assert "Auto-applying fix..." in captured.out

    def test_auto_apply_abort(self, mock_suggestions, capsys):
        """Test aborting auto-apply at confirmation."""
        # Mock the analyzer service
        mock_service = MagicMock()

        # Mock user input to abort auto-apply
        with patch("builtins.input", return_value="n"):
            # Run interactive apply with auto_apply=True
            apply_suggestions_interactively(
                mock_suggestions, mock_service, MagicMock(auto_apply=True)
            )

            # Check that apply_suggestion was NOT called
            mock_service.apply_suggestion.assert_not_called()

            # Check output
            captured = capsys.readouterr()
            assert "AUTO-APPLY MODE ENABLED" in captured.out
            assert "Aborting auto-apply mode" in captured.out


if __name__ == "__main__":
    pytest.main(["-v", __file__])
