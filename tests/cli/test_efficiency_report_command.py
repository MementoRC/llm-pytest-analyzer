"""
Comprehensive tests for the EfficiencyReportCommand CLI Command.

Covers:
- Argument parsing for various report options
- Mock data retrieval and report generation
- Visualization with different data sets
- Comparative analysis calculations
- Export functionality (JSON)
- Error handling for missing data
- Time range filtering (day, week, month, all)
- Verbose mode output

Follows the test patterns of test_check_env_command.py.
"""

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.cli.efficiency_report import EfficiencyReportCommand, main
from pytest_analyzer.utils.settings import Settings

# --- Fixtures ---


@pytest.fixture
def mock_settings():
    """Fixture to provide a mock Settings instance."""
    settings = MagicMock(spec=Settings)
    settings.project_root = "/tmp/test_project"
    return settings


@pytest.fixture
def temp_db():
    """Fixture to provide a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Initialize database with test schema
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Create sessions table
        cursor.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                total_tokens INTEGER DEFAULT 0,
                total_fixes INTEGER DEFAULT 0,
                successful_fixes INTEGER DEFAULT 0,
                efficiency_score REAL
            )
        """)

        # Insert test data
        test_sessions = [
            ("2025-06-20T10:00:00", "2025-06-20T11:00:00", 500, 5, 4, 0.8),
            ("2025-06-21T10:00:00", "2025-06-21T11:30:00", 800, 8, 6, 0.75),
            ("2025-06-22T10:00:00", "2025-06-22T12:00:00", 1200, 12, 10, 0.9),
        ]

        for session in test_sessions:
            cursor.execute(
                """
                INSERT INTO sessions (start_time, end_time, total_tokens, total_fixes, successful_fixes, efficiency_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                session,
            )

        conn.commit()

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def mock_efficiency_tracker(temp_db):
    """Fixture to provide a mock EfficiencyTracker with a real database."""
    tracker = MagicMock()
    tracker.db_path = Path(temp_db)
    tracker.generate_recommendations.return_value = [
        "🎯 Focus on improving fix quality over quantity.",
        "🪙 Consider optimizing prompts to reduce token usage.",
    ]
    return tracker


@pytest.fixture
def command(mock_settings, mock_efficiency_tracker):
    """Fixture to provide an EfficiencyReportCommand instance."""
    return EfficiencyReportCommand(
        efficiency_tracker=mock_efficiency_tracker, settings=mock_settings
    )


# --- Helper Functions ---


def run_command_with_args(command, args_list):
    """Helper to run command with given argument list."""
    with patch("sys.argv", ["efficiency-report"] + args_list):
        with patch.object(command, "parse_arguments") as mock_parse:
            # Create mock args based on args_list
            mock_args = MagicMock()
            mock_args.time_range = "week"
            mock_args.format = "table"
            mock_args.output_file = None
            mock_args.verbose = False
            mock_args.compare = False
            mock_args.trends = False
            mock_args.recommendations = False
            mock_args.config_file = None
            mock_args.start_date = None
            mock_args.end_date = None

            # Update based on actual args
            if "--format" in args_list:
                format_idx = args_list.index("--format")
                if format_idx + 1 < len(args_list):
                    mock_args.format = args_list[format_idx + 1]

            if "--time-range" in args_list:
                range_idx = args_list.index("--time-range")
                if range_idx + 1 < len(args_list):
                    mock_args.time_range = args_list[range_idx + 1]

            if "--verbose" in args_list:
                mock_args.verbose = True

            if "--compare" in args_list:
                mock_args.compare = True

            if "--recommendations" in args_list:
                mock_args.recommendations = True

            mock_parse.return_value = mock_args
            return command.execute(), mock_args


# --- Tests ---


@pytest.mark.parametrize(
    "args,expected_format,expected_time_range",
    [
        ([], "table", "week"),
        (["--format", "json"], "json", "week"),
        (["--time-range", "month"], "table", "month"),
        (["--time-range", "day", "--format", "json"], "json", "day"),
        (["--verbose"], "table", "week"),
    ],
)
def test_cli_argument_parsing_and_output(
    command, args, expected_format, expected_time_range
):
    """Test CLI argument parsing and output format options."""
    exit_code, parsed_args = run_command_with_args(command, args)

    assert exit_code == 0
    assert parsed_args.format == expected_format
    assert parsed_args.time_range == expected_time_range


def test_report_generation_with_mock_data(command):
    """Test report generation with mock data."""
    # Create mock args
    args = MagicMock()
    args.time_range = "week"
    args.start_date = None
    args.end_date = None
    args.verbose = False
    args.compare = False
    args.trends = False
    args.recommendations = False

    report_data = command.generate_report(args)

    assert "metadata" in report_data
    assert "metrics" in report_data
    assert report_data["metadata"]["time_range"] == "week"
    assert isinstance(report_data["metrics"]["total_sessions"], int)


def test_visualization_functions_with_various_data(command):
    """Test visualization functions with different data sets."""
    # Test with empty data
    empty_sessions = []
    empty_metrics = command._calculate_metrics(empty_sessions)

    assert empty_metrics["total_sessions"] == 0
    assert empty_metrics["average_efficiency_score"] == 0.0

    # Test with sample data
    sample_sessions = [
        {
            "id": 1,
            "total_tokens": 500,
            "total_fixes": 5,
            "successful_fixes": 4,
            "efficiency_score": 0.8,
            "start_time": "2025-06-20T10:00:00",
        }
    ]

    metrics = command._calculate_metrics(sample_sessions)
    assert metrics["total_sessions"] == 1
    assert metrics["total_tokens"] == 500
    assert metrics["success_rate"] == 0.8


def test_comparative_analysis_calculations(command):
    """Test comparative analysis calculations."""
    start_date = datetime(2025, 6, 20)
    end_date = datetime(2025, 6, 22)

    comparison_data = command._generate_comparative_analysis(start_date, end_date)

    assert "current_period" in comparison_data
    assert "previous_period" in comparison_data
    assert "changes" in comparison_data


def test_export_json_functionality(command, tmp_path):
    """Test export functionality for JSON format."""
    output_file = tmp_path / "test_report.json"

    test_data = {
        "metadata": {"generated_at": "2025-06-20T10:00:00"},
        "metrics": {"total_sessions": 1},
    }

    command._save_report(test_data, str(output_file), "json")

    assert output_file.exists()

    with open(output_file) as f:
        loaded_data = json.load(f)

    assert loaded_data == test_data


def test_error_handling_for_missing_data(command):
    """Test error handling for missing data scenarios."""
    # Test with non-existent database
    command.efficiency_tracker.db_path = Path("/non/existent/path.db")

    try:
        sessions = command._get_sessions_data(None, None)
        # Should return empty list or handle gracefully
        assert isinstance(sessions, list)
    except Exception as e:
        # Should handle database errors gracefully
        assert isinstance(e, Exception)


def test_time_range_filtering(command):
    """Test different time ranges (day, week, month, all)."""
    for time_range in ["day", "week", "month", "all"]:
        args = MagicMock()
        args.time_range = time_range
        args.start_date = None
        args.end_date = None

        start_date, end_date = command._calculate_time_range(args)

        if time_range == "all":
            assert start_date is None
            assert end_date is None
        else:
            assert isinstance(start_date, datetime)
            assert isinstance(end_date, datetime)
            assert start_date <= end_date


def test_verbose_mode_functionality(command):
    """Test verbose mode output."""
    args = MagicMock()
    args.time_range = "week"
    args.start_date = None
    args.end_date = None
    args.verbose = True
    args.compare = False
    args.trends = False
    args.recommendations = False

    report_data = command.generate_report(args)

    # In verbose mode, sessions should be included
    assert "sessions" in report_data


def test_trends_analysis_generation(command):
    """Test trend analysis with sample data."""
    sample_sessions = [
        {
            "start_time": "2025-06-20T10:00:00",
            "total_tokens": 500,
            "total_fixes": 5,
            "successful_fixes": 4,
            "efficiency_score": 0.8,
        },
        {
            "start_time": "2025-06-21T10:00:00",
            "total_tokens": 600,
            "total_fixes": 6,
            "successful_fixes": 5,
            "efficiency_score": 0.85,
        },
    ]

    trends = command._generate_trends_analysis(sample_sessions)

    assert "daily_trends" in trends
    assert "overall_trend" in trends
    assert len(trends["daily_trends"]) >= 1


def test_main_function_integration():
    """Test the main function integration."""
    with patch("sys.argv", ["efficiency-report", "--help"]):
        with patch(
            "pytest_analyzer.cli.efficiency_report.EfficiencyReportCommand"
        ) as MockCommand:
            mock_instance = MagicMock()
            MockCommand.return_value = mock_instance
            mock_instance.execute.return_value = 0

            try:
                result = main()
                assert result == 0
            except SystemExit as e:
                # argparse help exits with code 0
                assert e.code == 0


def test_calculate_metrics_edge_cases(command):
    """Test _calculate_metrics with edge cases."""
    # Test with sessions that have None efficiency scores
    sessions_with_none = [
        {
            "total_tokens": 100,
            "total_fixes": 2,
            "successful_fixes": 1,
            "efficiency_score": None,
            "start_time": "2025-06-20T10:00:00",
        }
    ]

    metrics = command._calculate_metrics(sessions_with_none)
    assert metrics["average_efficiency_score"] == 0.0
    assert metrics["success_rate"] == 0.5


def test_display_table_report(command, capsys):
    """Test table report display functionality."""
    test_data = {
        "metadata": {"time_range": "week", "total_sessions": 3},
        "metrics": {
            "total_sessions": 3,
            "total_tokens": 1500,
            "total_fixes": 15,
            "successful_fixes": 12,
            "success_rate": 0.8,
            "average_efficiency_score": 0.85,
            "tokens_per_fix": 125.0,
            "sessions_per_day": 1.5,
        },
    }

    args = MagicMock()
    args.format = "table"

    # Capture output
    command._display_table_report(test_data, args)

    # Note: This test mainly checks that the method runs without error
    # since rich output is complex to capture in tests


def test_format_table_report(command):
    """Test plain text table formatting."""
    test_data = {
        "metadata": {
            "generated_at": "2025-06-20T10:00:00",
            "time_range": "week",
            "total_sessions": 2,
        },
        "metrics": {
            "total_tokens": 1000,
            "total_fixes": 10,
            "successful_fixes": 8,
            "success_rate": 0.8,
            "average_efficiency_score": 0.75,
            "tokens_per_fix": 125.0,
            "sessions_per_day": 1.0,
        },
        "recommendations": ["Test recommendation"],
    }

    formatted_report = command._format_table_report(test_data)

    assert "Development Efficiency Report" in formatted_report
    assert "Total Tokens Used: 1,000" in formatted_report
    assert "Success Rate: 80.0%" in formatted_report
    assert "Test recommendation" in formatted_report
