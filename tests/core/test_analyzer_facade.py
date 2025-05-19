"""Tests for the backward-compatibility facade implementation."""

from unittest.mock import MagicMock, patch

from pytest_analyzer.core.analyzer_facade import PytestAnalyzerFacade
from pytest_analyzer.core.backward_compat import PytestAnalyzerService
from pytest_analyzer.core.models.pytest_failure import FixSuggestion
from pytest_analyzer.utils.settings import Settings


class TestAnalyzerFacade:
    """Tests for the backward-compatibility facade."""

    def test_facade_init(self):
        """Test that the facade initializes correctly."""
        # Create a settings object
        settings = Settings()

        # Create the facade
        facade = PytestAnalyzerFacade(settings=settings)

        # Verify that the facade has been initialized correctly
        assert facade.settings is settings
        assert facade.di_container is not None

    def test_backward_compat_class(self):
        """Test that the backward-compatibility class redirects to the facade."""
        # Create a settings object
        settings = Settings()

        # Create the service using the legacy name
        service = PytestAnalyzerService(settings=settings)

        # Verify that it's actually a facade
        assert isinstance(service, PytestAnalyzerFacade)
        assert service.settings is settings
        assert service.di_container is not None

    @patch("pytest_analyzer.core.analyzer_state_machine.AnalyzerStateMachine")
    def test_analyze_pytest_output(self, mock_state_machine_class):
        """Test the analyze_pytest_output method."""
        # Setup mock state machine
        mock_state_machine = MagicMock()
        mock_state_machine_class.return_value = mock_state_machine

        # Mock the run method to return a result with suggestions
        mock_suggestion = MagicMock(spec=FixSuggestion)
        mock_state_machine.run.return_value = {"suggestions": [mock_suggestion]}

        # Create the facade
        facade = PytestAnalyzerFacade()

        # Mock the path existence check
        with patch("pathlib.Path.exists", return_value=True):
            # Call the method
            suggestions = facade.analyze_pytest_output("fake_output.json")

            # Verify the result
            assert len(suggestions) == 1
            assert suggestions[0] is mock_suggestion

            # Verify state machine was called correctly
            mock_state_machine_class.assert_called_once()
            mock_state_machine.run.assert_called_once_with(
                test_results_path="fake_output.json", apply_fixes=False
            )

    @patch("pytest_analyzer.core.analyzer_state_machine.AnalyzerStateMachine")
    def test_run_pytest_only(self, mock_state_machine_class):
        """Test the run_pytest_only method."""
        # Setup mock state machine
        mock_state_machine = MagicMock()
        mock_state_machine_class.return_value = mock_state_machine

        # Mock the run method to return a result with extraction results
        mock_failure = MagicMock()
        mock_state_machine.run.return_value = {
            "extraction_results": {"failures": [mock_failure]}
        }

        # Create the facade
        facade = PytestAnalyzerFacade()

        # Call the method
        failures = facade.run_pytest_only("test_path", ["--verbose"], quiet=True)

        # Verify the result
        assert len(failures) == 1
        assert failures[0] is mock_failure

        # Verify state machine was called correctly
        mock_state_machine_class.assert_called_once()
        mock_state_machine.run.assert_called_once_with(
            test_path="test_path",
            pytest_args=["--verbose"],
            quiet=True,
            extract_only=True,
        )

    @patch("pytest_analyzer.core.analyzer_state_machine.AnalyzerStateMachine")
    def test_run_and_analyze(self, mock_state_machine_class):
        """Test the run_and_analyze method."""
        # Setup mock state machine
        mock_state_machine = MagicMock()
        mock_state_machine_class.return_value = mock_state_machine

        # Mock the run method to return a result with suggestions
        mock_suggestion = MagicMock(spec=FixSuggestion)
        mock_state_machine.run.return_value = {"suggestions": [mock_suggestion]}

        # Create the facade
        facade = PytestAnalyzerFacade()

        # Call the method
        suggestions = facade.run_and_analyze("test_path", ["--verbose"], quiet=True)

        # Verify the result
        assert len(suggestions) == 1
        assert suggestions[0] is mock_suggestion

        # Verify state machine was called correctly
        mock_state_machine_class.assert_called_once()
        mock_state_machine.run.assert_called_once_with(
            test_path="test_path",
            pytest_args=["--verbose"],
            quiet=True,
            apply_fixes=False,
        )

    @patch("pytest_analyzer.core.protocols.Applier")
    def test_apply_suggestion(self, mock_applier_class):
        """Test the apply_suggestion method."""
        # Setup mock applier
        mock_applier = MagicMock()
        mock_applier.apply.return_value = {
            "success": True,
            "message": "Fix applied successfully",
            "applied_files": ["file1.py"],
            "rolled_back_files": [],
        }

        # Create the facade with mocked DI container
        facade = PytestAnalyzerFacade()
        facade.di_container = MagicMock()
        facade.di_container.resolve.return_value = mock_applier

        # Create a mock suggestion
        mock_suggestion = MagicMock(spec=FixSuggestion)
        mock_suggestion.code_changes = {
            "file1.py": "new content",
            "source": "llm",  # Should be filtered out
        }
        mock_suggestion.failure.test_name = "test_function"

        # Call the method
        result = facade.apply_suggestion(mock_suggestion)

        # Verify the result
        assert result["success"] is True
        assert result["message"] == "Fix applied successfully"
        assert result["applied_files"] == ["file1.py"]
        assert result["rolled_back_files"] == []

        # Verify applier was called correctly
        mock_applier.apply.assert_called_once_with(
            {"file1.py": "new content"}, ["test_function"]
        )

    @patch("pytest_analyzer.core.analyzer_state_machine.AnalyzerStateMachine")
    def test_error_handling(self, mock_state_machine_class):
        """Test error handling in the facade methods."""
        # Setup mock state machine
        mock_state_machine = MagicMock()
        mock_state_machine_class.return_value = mock_state_machine

        # Mock the run method to raise an exception
        mock_state_machine.run.side_effect = ValueError("Test error")

        # Create the facade
        facade = PytestAnalyzerFacade()

        # Mock the path existence check
        with patch("pathlib.Path.exists", return_value=True):
            # Call the methods and verify they handle exceptions
            suggestions = facade.analyze_pytest_output("fake_output.json")
            assert suggestions == []

            failures = facade.run_pytest_only("test_path")
            assert failures == []

            suggestions = facade.run_and_analyze("test_path")
            assert suggestions == []
