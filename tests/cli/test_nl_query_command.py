from unittest.mock import MagicMock, patch

from pytest_analyzer.cli.nl_query import main


def test_cli_help():
    """Test the CLI main function with help intent."""
    with patch("sys.argv", ["nl_query", "help"]):
        with patch("pytest_analyzer.cli.nl_query.console") as mock_console:
            with patch(
                "pytest_analyzer.cli.nl_query.NLQueryProcessor"
            ) as mock_processor:
                with patch(
                    "pytest_analyzer.cli.nl_query.NLResponseGenerator"
                ) as mock_generator:
                    mock_processor_instance = MagicMock()
                    mock_processor.return_value = mock_processor_instance
                    mock_processor_instance.process_query.return_value = {
                        "intent": "help",
                        "response": "You can ask about test failures, request fix suggestions",
                    }
                    mock_generator_instance = MagicMock()
                    mock_generator.return_value = mock_generator_instance
                    mock_generator_instance.generate.return_value = (
                        "You can ask about test failures"
                    )

                    result = main()

                    assert result == 0
                    mock_console.print.assert_called()


def test_cli_autocomplete():
    """Test the CLI main function with autocomplete."""
    with patch("sys.argv", ["nl_query", "--autocomplete", "show"]):
        with patch("pytest_analyzer.cli.nl_query.console") as mock_console:
            with patch(
                "pytest_analyzer.cli.nl_query.NLQueryProcessor"
            ) as mock_processor:
                mock_processor_instance = MagicMock()
                mock_processor.return_value = mock_processor_instance
                mock_processor_instance.suggest_autocomplete.return_value = [
                    "show tests",
                    "show coverage",
                ]

                result = main()

                assert result == 0
                mock_console.print.assert_called()
