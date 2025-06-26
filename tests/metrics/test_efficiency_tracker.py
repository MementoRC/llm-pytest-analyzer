"""
Comprehensive tests for the EfficiencyTracker class.

Tests TaskMaster Task 6 implementation including:
- Session lifecycle management (start_session, end_session)
- Token consumption tracking (track_token_consumption)
- Auto-fix recording (record_auto_fix)
- Efficiency score calculation (calculate_efficiency_score)
- Recommendation generation (generate_recommendations)
"""

import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from pytest_analyzer.core.cross_cutting.monitoring.metrics import ApplicationMetrics
from pytest_analyzer.metrics.efficiency_tracker import (
    AutoFixRecord,
    EfficiencyTracker,
    EfficiencyTrackerError,
    Session,
    TokenUsage,
)
from pytest_analyzer.utils.settings import Settings


@pytest.fixture
def temp_db_path():
    """Provides a temporary database path for testing."""
    with TemporaryDirectory() as temp_dir:
        yield Path(temp_dir) / "test_efficiency.db"


@pytest.fixture
def mock_settings(temp_db_path):
    """Creates a mock Settings object."""
    settings = Mock(spec=Settings)
    settings.project_root = temp_db_path.parent
    return settings


@pytest.fixture
def mock_metrics():
    """Creates a mock ApplicationMetrics object."""
    return Mock(spec=ApplicationMetrics)


@pytest.fixture
def efficiency_tracker(mock_settings, mock_metrics):
    """Creates an EfficiencyTracker instance for testing."""
    return EfficiencyTracker(mock_settings, mock_metrics)


class TestEfficiencyTrackerInit:
    """Tests for EfficiencyTracker initialization."""

    def test_initialization(self, efficiency_tracker, mock_settings, temp_db_path):
        """Test EfficiencyTracker initialization."""
        assert efficiency_tracker.settings == mock_settings
        assert (
            efficiency_tracker.db_path == temp_db_path.parent / "efficiency_metrics.db"
        )
        assert efficiency_tracker._current_session_id is None

    def test_database_schema_creation(self, efficiency_tracker):
        """Test that database schema is created correctly."""
        # Verify database file exists
        assert efficiency_tracker.db_path.exists()

        # Verify tables exist
        with sqlite3.connect(efficiency_tracker.db_path) as conn:
            cursor = conn.cursor()

            # Check sessions table
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
            )
            assert cursor.fetchone() is not None

            # Check token_usage table
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='token_usage'"
            )
            assert cursor.fetchone() is not None

            # Check autofix_records table
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='autofix_records'"
            )
            assert cursor.fetchone() is not None


class TestSessionLifecycle:
    """Tests for session lifecycle management."""

    def test_start_session(self, efficiency_tracker):
        """Test starting a new session."""
        session_id = efficiency_tracker.start_session()

        assert session_id > 0
        assert efficiency_tracker._current_session_id == session_id

        # Verify session was stored in database
        with sqlite3.connect(efficiency_tracker.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, start_time FROM sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == session_id

    def test_start_session_when_active_raises_error(self, efficiency_tracker):
        """Test that starting a session when one is active raises error."""
        efficiency_tracker.start_session()

        with pytest.raises(EfficiencyTrackerError, match="Session already active"):
            efficiency_tracker.start_session()

    def test_end_session(self, efficiency_tracker):
        """Test ending a session."""
        session_id = efficiency_tracker.start_session()

        # Add some test data
        efficiency_tracker.track_token_consumption(100)
        efficiency_tracker.record_auto_fix(True)

        score = efficiency_tracker.end_session()

        assert 0.0 <= score <= 1.0
        assert efficiency_tracker._current_session_id is None

        # Verify session was updated in database
        with sqlite3.connect(efficiency_tracker.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT end_time, efficiency_score FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] is not None  # end_time
            assert row[1] == score  # efficiency_score

    def test_end_session_without_active_raises_error(self, efficiency_tracker):
        """Test that ending session without active session raises error."""
        with pytest.raises(EfficiencyTrackerError, match="No active session"):
            efficiency_tracker.end_session()


class TestTokenTracking:
    """Tests for token consumption tracking."""

    def test_track_token_consumption(self, efficiency_tracker):
        """Test tracking token consumption."""
        session_id = efficiency_tracker.start_session()

        efficiency_tracker.track_token_consumption(150)

        # Verify token usage was recorded
        with sqlite3.connect(efficiency_tracker.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT tokens FROM token_usage WHERE session_id = ?", (session_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 150

            # Verify session totals were updated
            cursor.execute(
                "SELECT total_tokens FROM sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
            assert row[0] == 150

    def test_track_multiple_token_consumptions(self, efficiency_tracker):
        """Test tracking multiple token consumptions accumulates correctly."""
        session_id = efficiency_tracker.start_session()

        efficiency_tracker.track_token_consumption(50)
        efficiency_tracker.track_token_consumption(75)
        efficiency_tracker.track_token_consumption(25)

        # Verify total tokens
        with sqlite3.connect(efficiency_tracker.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT total_tokens FROM sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
            assert row[0] == 150

    def test_track_token_consumption_invalid_values(self, efficiency_tracker):
        """Test that invalid token values raise errors."""
        efficiency_tracker.start_session()

        with pytest.raises(
            EfficiencyTrackerError, match="Token count must be positive"
        ):
            efficiency_tracker.track_token_consumption(0)

        with pytest.raises(
            EfficiencyTrackerError, match="Token count must be positive"
        ):
            efficiency_tracker.track_token_consumption(-10)

    def test_track_token_consumption_no_active_session(self, efficiency_tracker):
        """Test that tracking tokens without active session logs warning but doesn't crash."""
        # Should not raise exception
        efficiency_tracker.track_token_consumption(100)


class TestAutoFixRecording:
    """Tests for auto-fix recording."""

    def test_record_auto_fix_success(self, efficiency_tracker):
        """Test recording successful auto-fix."""
        session_id = efficiency_tracker.start_session()

        efficiency_tracker.record_auto_fix(True)

        # Verify auto-fix was recorded
        with sqlite3.connect(efficiency_tracker.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT success FROM autofix_records WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 1  # True stored as 1

            # Verify session totals were updated
            cursor.execute(
                "SELECT total_fixes, successful_fixes FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            assert row[0] == 1  # total_fixes
            assert row[1] == 1  # successful_fixes

    def test_record_auto_fix_failure(self, efficiency_tracker):
        """Test recording failed auto-fix."""
        session_id = efficiency_tracker.start_session()

        efficiency_tracker.record_auto_fix(False)

        # Verify auto-fix was recorded
        with sqlite3.connect(efficiency_tracker.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT success FROM autofix_records WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 0  # False stored as 0

            # Verify session totals were updated
            cursor.execute(
                "SELECT total_fixes, successful_fixes FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            assert row[0] == 1  # total_fixes
            assert row[1] == 0  # successful_fixes

    def test_record_multiple_auto_fixes(self, efficiency_tracker):
        """Test recording multiple auto-fixes accumulates correctly."""
        session_id = efficiency_tracker.start_session()

        efficiency_tracker.record_auto_fix(True)
        efficiency_tracker.record_auto_fix(False)
        efficiency_tracker.record_auto_fix(True)

        # Verify totals
        with sqlite3.connect(efficiency_tracker.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT total_fixes, successful_fixes FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            assert row[0] == 3  # total_fixes
            assert row[1] == 2  # successful_fixes

    def test_record_auto_fix_no_active_session(self, efficiency_tracker):
        """Test that recording auto-fix without active session logs warning but doesn't crash."""
        # Should not raise exception
        efficiency_tracker.record_auto_fix(True)


class TestEfficiencyScoreCalculation:
    """Tests for efficiency score calculation."""

    def test_calculate_efficiency_score_no_active_session(self, efficiency_tracker):
        """Test that calculating score without active session raises error."""
        with pytest.raises(EfficiencyTrackerError, match="No active session"):
            efficiency_tracker.calculate_efficiency_score()

    def test_calculate_efficiency_score_no_data(self, efficiency_tracker):
        """Test efficiency score calculation with no data."""
        efficiency_tracker.start_session()
        score = efficiency_tracker.calculate_efficiency_score()
        assert score == 0.0

    def test_calculate_efficiency_score_perfect_session(self, efficiency_tracker):
        """Test efficiency score calculation for a perfect session."""
        efficiency_tracker.start_session()

        # Add minimal tokens and successful fixes
        efficiency_tracker.track_token_consumption(50)
        efficiency_tracker.record_auto_fix(True)

        score = efficiency_tracker.calculate_efficiency_score()
        assert 0.0 <= score <= 1.0

    def test_calculate_efficiency_score_mixed_results(self, efficiency_tracker):
        """Test efficiency score calculation with mixed results."""
        efficiency_tracker.start_session()

        # Add some data
        efficiency_tracker.track_token_consumption(200)
        efficiency_tracker.record_auto_fix(True)
        efficiency_tracker.record_auto_fix(False)
        efficiency_tracker.record_auto_fix(True)

        score = efficiency_tracker.calculate_efficiency_score()
        assert 0.0 <= score <= 1.0

    @pytest.mark.parametrize(
        "tokens,successful_fixes,total_fixes",
        [
            (100, 5, 5),  # High efficiency
            (500, 2, 5),  # Mixed efficiency
            (1000, 1, 10),  # Low efficiency
        ],
    )
    def test_efficiency_score_ranges(
        self, efficiency_tracker, tokens, successful_fixes, total_fixes
    ):
        """Test efficiency scores for various scenarios."""
        efficiency_tracker.start_session()

        efficiency_tracker.track_token_consumption(tokens)
        for i in range(total_fixes):
            success = i < successful_fixes
            efficiency_tracker.record_auto_fix(success)

        score = efficiency_tracker.calculate_efficiency_score()
        assert 0.0 <= score <= 1.0


class TestRecommendationGeneration:
    """Tests for recommendation generation."""

    def test_generate_recommendations_no_data(self, efficiency_tracker):
        """Test recommendation generation with no data."""
        recommendations = efficiency_tracker.generate_recommendations()
        assert len(recommendations) > 0
        assert any("No efficiency data available" in rec for rec in recommendations)

    def test_generate_recommendations_active_session(self, efficiency_tracker):
        """Test recommendation generation for active session."""
        efficiency_tracker.start_session()
        efficiency_tracker.track_token_consumption(100)
        efficiency_tracker.record_auto_fix(True)

        recommendations = efficiency_tracker.generate_recommendations()
        assert len(recommendations) > 0
        assert all(isinstance(rec, str) for rec in recommendations)

    def test_generate_recommendations_completed_session(self, efficiency_tracker):
        """Test recommendation generation for completed session."""
        efficiency_tracker.start_session()
        efficiency_tracker.track_token_consumption(100)
        efficiency_tracker.record_auto_fix(True)
        efficiency_tracker.end_session()

        recommendations = efficiency_tracker.generate_recommendations()
        assert len(recommendations) > 0
        assert all(isinstance(rec, str) for rec in recommendations)

    def test_generate_recommendations_low_efficiency(self, efficiency_tracker):
        """Test recommendations for low efficiency session."""
        efficiency_tracker.start_session()
        efficiency_tracker.track_token_consumption(1000)  # High tokens
        efficiency_tracker.record_auto_fix(False)  # Failed fix
        efficiency_tracker.end_session()

        recommendations = efficiency_tracker.generate_recommendations()
        assert any(
            "Low efficiency" in rec or "Low fix success" in rec
            for rec in recommendations
        )

    def test_generate_recommendations_high_efficiency(self, efficiency_tracker):
        """Test recommendations for high efficiency session."""
        # Create historical data first for comparison
        for _ in range(3):
            efficiency_tracker.start_session()
            efficiency_tracker.track_token_consumption(200)
            efficiency_tracker.record_auto_fix(True)
            efficiency_tracker.record_auto_fix(True)
            efficiency_tracker.end_session()

        # Current high-efficiency session
        efficiency_tracker.start_session()
        efficiency_tracker.track_token_consumption(50)  # Low tokens
        efficiency_tracker.record_auto_fix(True)  # Successful fix
        efficiency_tracker.end_session()

        recommendations = efficiency_tracker.generate_recommendations()
        assert any(
            "Great efficiency" in rec or "excellent" in rec for rec in recommendations
        )


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_sessions(self, efficiency_tracker):
        """Test that concurrent session operations are thread-safe."""
        session_ids = []
        errors = []

        def start_and_end_session():
            try:
                # Each thread gets its own tracker instance
                tracker = EfficiencyTracker(
                    efficiency_tracker.settings, efficiency_tracker.metrics_client
                )
                session_id = tracker.start_session()
                session_ids.append(session_id)

                # Add some data
                tracker.track_token_consumption(100)
                tracker.record_auto_fix(True)
                time.sleep(0.01)  # Small delay

                tracker.end_session()
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=start_and_end_session)
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify no errors and unique session IDs
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(session_ids) == 5
        assert len(set(session_ids)) == 5  # All unique


class TestDataModels:
    """Tests for data model classes."""

    def test_session_dataclass(self):
        """Test Session dataclass."""
        session = Session()
        assert session.id is None
        assert isinstance(session.start_time, datetime)
        assert session.end_time is None
        assert session.total_tokens == 0
        assert session.total_fixes == 0
        assert session.successful_fixes == 0
        assert session.efficiency_score is None

    def test_token_usage_dataclass(self):
        """Test TokenUsage dataclass."""
        token_usage = TokenUsage(session_id=1, tokens=100)
        assert token_usage.session_id == 1
        assert token_usage.tokens == 100
        assert isinstance(token_usage.timestamp, datetime)

    def test_autofix_record_dataclass(self):
        """Test AutoFixRecord dataclass."""
        autofix = AutoFixRecord(session_id=1, success=True)
        assert autofix.session_id == 1
        assert autofix.success is True
        assert isinstance(autofix.timestamp, datetime)


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_invalid_database_path(self, mock_metrics, tmp_path):
        """Test handling of invalid database paths."""
        invalid_settings = Mock(spec=Settings)
        # Use a path that doesn't require root permissions
        invalid_settings.project_root = tmp_path / "nonexistent" / "deeply" / "nested"

        # Should handle gracefully and create directories if needed
        tracker = EfficiencyTracker(invalid_settings, mock_metrics)
        assert tracker is not None
        assert tracker.db_path.parent.exists()  # Verify directory was created

    @patch("pytest_analyzer.metrics.efficiency_tracker.logger")
    def test_logging_behavior(self, mock_logger, efficiency_tracker):
        """Test that appropriate logging occurs."""
        efficiency_tracker.start_session()
        efficiency_tracker.end_session()

        # Verify info logs were called
        assert mock_logger.info.call_count >= 2


if __name__ == "__main__":
    pytest.main([__file__])
