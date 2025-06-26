"""
EfficiencyTracker implementation for development efficiency monitoring.

This module provides the EfficiencyTracker class according to TaskMaster Task 6 requirements:
- Session lifecycle management (start_session, end_session)
- Token consumption tracking (track_token_consumption)
- Auto-fix recording (record_auto_fix)
- Efficiency score calculation (calculate_efficiency_score)
- Recommendation generation (generate_recommendations)
"""

import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pytest_analyzer.core.cross_cutting.error_handling import (
    error_handler,
)
from pytest_analyzer.core.cross_cutting.monitoring.metrics import ApplicationMetrics
from pytest_analyzer.core.errors import BaseError
from pytest_analyzer.utils.settings import Settings

logger = logging.getLogger(__name__)

# Configuration Constants
DB_FILE_NAME = "efficiency_metrics.db"
MOVING_AVERAGE_WINDOW = 10
EFFICIENCY_WEIGHTS = {
    "token_efficiency": 0.4,
    "fix_success_rate": 0.3,
    "session_speed": 0.3,
}


class EfficiencyTrackerError(BaseError):
    """Base exception for EfficiencyTracker related errors."""

    pass


@dataclass
class Session:
    """Represents an efficiency tracking session."""

    id: Optional[int] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_tokens: int = 0
    total_fixes: int = 0
    successful_fixes: int = 0
    efficiency_score: Optional[float] = None


@dataclass
class TokenUsage:
    """Represents token consumption data."""

    session_id: int
    tokens: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AutoFixRecord:
    """Represents an auto-fix attempt."""

    session_id: int
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)


class EfficiencyTracker:
    """
    Tracks and measures development efficiency improvements.

    This class implements the TaskMaster Task 6 requirements:
    - Session lifecycle management
    - Token consumption tracking
    - Auto-fix success monitoring
    - Efficiency score calculation
    - Recommendation generation
    """

    def __init__(self, settings: Settings, metrics_client: ApplicationMetrics):
        """Initialize the EfficiencyTracker."""
        self.settings = settings
        self.metrics_client = metrics_client
        self.db_path = Path(self.settings.project_root) / DB_FILE_NAME
        self._lock = threading.Lock()
        self._current_session_id: Optional[int] = None
        self._init_database()
        logger.info(f"EfficiencyTracker initialized with database: {self.db_path}")

    def _init_database(self) -> None:
        """Initialize the SQLite database schema."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_tokens INTEGER DEFAULT 0,
                    total_fixes INTEGER DEFAULT 0,
                    successful_fixes INTEGER DEFAULT 0,
                    efficiency_score REAL
                )
            """)

            # Token usage table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    tokens INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)

            # Auto-fix records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS autofix_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)

            conn.commit()

    @error_handler(
        "start efficiency session", EfficiencyTrackerError, logger=logger, reraise=True
    )
    def start_session(self) -> int:
        """
        Start a new efficiency tracking session.

        Returns:
            Session ID for the newly started session.
        """
        with self._lock:
            if self._current_session_id is not None:
                raise EfficiencyTrackerError(
                    "Session already active. End current session first."
                )

            session = Session()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sessions (start_time) VALUES (?)",
                    (session.start_time.isoformat(),),
                )
                self._current_session_id = cursor.lastrowid

            logger.info(f"Started efficiency session {self._current_session_id}")
            return self._current_session_id

    @error_handler(
        "end efficiency session", EfficiencyTrackerError, logger=logger, reraise=True
    )
    def end_session(self) -> float:
        """
        End the current efficiency tracking session and calculate score.

        Returns:
            The calculated efficiency score (0.0-1.0).
        """
        with self._lock:
            if self._current_session_id is None:
                raise EfficiencyTrackerError("No active session to end.")

            session_id = self._current_session_id
            end_time = datetime.now()

            # Calculate efficiency score
            efficiency_score = self.calculate_efficiency_score()

            # Update session in database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE sessions
                    SET end_time = ?, efficiency_score = ?
                    WHERE id = ?
                """,
                    (end_time.isoformat(), efficiency_score, session_id),
                )

            logger.info(
                f"Ended session {session_id} with efficiency score: {efficiency_score:.3f}"
            )
            self._current_session_id = None
            return efficiency_score

    @error_handler(
        "track token consumption", EfficiencyTrackerError, logger=logger, reraise=True
    )
    def track_token_consumption(self, tokens: int) -> None:
        """
        Track LLM token consumption for the current session.

        Args:
            tokens: Number of tokens consumed.
        """
        if tokens <= 0:
            raise ValueError("Token count must be positive")

        with self._lock:
            if self._current_session_id is None:
                logger.warning("No active session - token consumption not tracked")
                return

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Record token usage
                cursor.execute(
                    """
                    INSERT INTO token_usage (session_id, tokens, timestamp)
                    VALUES (?, ?, ?)
                """,
                    (self._current_session_id, tokens, datetime.now().isoformat()),
                )

                # Update session totals
                cursor.execute(
                    """
                    UPDATE sessions
                    SET total_tokens = total_tokens + ?
                    WHERE id = ?
                """,
                    (tokens, self._current_session_id),
                )

            logger.debug(
                f"Tracked {tokens} tokens for session {self._current_session_id}"
            )

    @error_handler(
        "record auto fix", EfficiencyTrackerError, logger=logger, reraise=False
    )
    def record_auto_fix(self, success: bool) -> None:
        """
        Record an auto-fix attempt result.

        Args:
            success: Whether the auto-fix was successful.
        """
        with self._lock:
            if self._current_session_id is None:
                logger.warning("No active session - auto-fix not recorded")
                return

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Record auto-fix attempt
                cursor.execute(
                    """
                    INSERT INTO autofix_records (session_id, success, timestamp)
                    VALUES (?, ?, ?)
                """,
                    (
                        self._current_session_id,
                        1 if success else 0,
                        datetime.now().isoformat(),
                    ),
                )

                # Update session totals
                cursor.execute(
                    """
                    UPDATE sessions
                    SET total_fixes = total_fixes + 1,
                        successful_fixes = successful_fixes + ?
                    WHERE id = ?
                """,
                    (1 if success else 0, self._current_session_id),
                )

            logger.debug(
                f"Recorded auto-fix ({'success' if success else 'failure'}) for session {self._current_session_id}"
            )

    @error_handler(
        "calculate efficiency score",
        EfficiencyTrackerError,
        logger=logger,
        reraise=True,
    )
    def calculate_efficiency_score(self) -> float:
        """
        Calculate efficiency score for the current session.

        Returns:
            Efficiency score between 0.0 and 1.0.
        """
        if self._current_session_id is None:
            raise EfficiencyTrackerError("No active session for score calculation")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get current session data
            cursor.execute(
                """
                SELECT total_tokens, total_fixes, successful_fixes, start_time
                FROM sessions WHERE id = ?
            """,
                (self._current_session_id,),
            )

            row = cursor.fetchone()
            if not row:
                return 0.0

            total_tokens, total_fixes, successful_fixes, start_time = row

            # Calculate component scores
            token_efficiency = self._calculate_token_efficiency(
                total_tokens, successful_fixes
            )
            fix_success_rate = self._calculate_fix_success_rate(
                total_fixes, successful_fixes
            )
            session_speed = self._calculate_session_speed(start_time, total_fixes)

            # Weighted average
            efficiency_score = (
                EFFICIENCY_WEIGHTS["token_efficiency"] * token_efficiency
                + EFFICIENCY_WEIGHTS["fix_success_rate"] * fix_success_rate
                + EFFICIENCY_WEIGHTS["session_speed"] * session_speed
            )

            return max(0.0, min(1.0, efficiency_score))

    def _calculate_token_efficiency(
        self, total_tokens: int, successful_fixes: int
    ) -> float:
        """Calculate token efficiency component (lower tokens per fix is better)."""
        if successful_fixes == 0:
            return 0.0

        tokens_per_fix = total_tokens / successful_fixes

        # Use historical average for normalization
        historical_avg = self._get_historical_average_tokens_per_fix()
        if historical_avg == 0:
            return 0.5  # Neutral score if no history

        # Better efficiency = lower tokens per fix
        efficiency = historical_avg / tokens_per_fix if tokens_per_fix > 0 else 0.0
        return min(1.0, efficiency)

    def _calculate_fix_success_rate(
        self, total_fixes: int, successful_fixes: int
    ) -> float:
        """Calculate fix success rate component."""
        if total_fixes == 0:
            return 0.0
        return successful_fixes / total_fixes

    def _calculate_session_speed(self, start_time: str, total_fixes: int) -> float:
        """Calculate session speed component (more fixes per time is better)."""
        if total_fixes == 0:
            return 0.0

        start_dt = datetime.fromisoformat(start_time)
        duration_hours = (datetime.now() - start_dt).total_seconds() / 3600

        if duration_hours == 0:
            return 1.0

        fixes_per_hour = total_fixes / duration_hours

        # Use historical average for normalization
        historical_avg = self._get_historical_average_fixes_per_hour()
        if historical_avg == 0:
            return 0.5  # Neutral score if no history

        speed_efficiency = fixes_per_hour / historical_avg
        return min(1.0, speed_efficiency)

    def _get_historical_average_tokens_per_fix(self) -> float:
        """Get historical average tokens per successful fix."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT AVG(CAST(total_tokens AS FLOAT) / successful_fixes)
                FROM sessions
                WHERE successful_fixes > 0 AND end_time IS NOT NULL
                ORDER BY start_time DESC
                LIMIT ?
            """,
                (MOVING_AVERAGE_WINDOW,),
            )

            result = cursor.fetchone()
            return result[0] if result[0] else 100.0  # Default baseline

    def _get_historical_average_fixes_per_hour(self) -> float:
        """Get historical average fixes per hour."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT AVG(
                    CAST(total_fixes AS FLOAT) /
                    ((julianday(end_time) - julianday(start_time)) * 24)
                )
                FROM sessions
                WHERE end_time IS NOT NULL AND total_fixes > 0
                ORDER BY start_time DESC
                LIMIT ?
            """,
                (MOVING_AVERAGE_WINDOW,),
            )

            result = cursor.fetchone()
            return result[0] if result[0] else 1.0  # Default baseline

    @error_handler(
        "generate recommendations", EfficiencyTrackerError, logger=logger, reraise=True
    )
    def generate_recommendations(self) -> List[str]:
        """
        Generate actionable recommendations based on efficiency data.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        if self._current_session_id is None:
            # Get latest completed session
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT efficiency_score, total_tokens, total_fixes, successful_fixes
                    FROM sessions
                    WHERE end_time IS NOT NULL
                    ORDER BY start_time DESC
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if not row:
                    return ["No efficiency data available. Complete a session first."]

                efficiency_score, total_tokens, total_fixes, successful_fixes = row
        else:
            # Use current session data
            efficiency_score = self.calculate_efficiency_score()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT total_tokens, total_fixes, successful_fixes
                    FROM sessions WHERE id = ?
                """,
                    (self._current_session_id,),
                )
                row = cursor.fetchone()
                total_tokens, total_fixes, successful_fixes = row

        # Generate recommendations based on efficiency score and metrics
        if efficiency_score < 0.3:
            recommendations.append(
                "⚠️ Low efficiency detected. Consider reviewing your approach."
            )

        if total_fixes > 0 and successful_fixes / total_fixes < 0.5:
            recommendations.append(
                "🎯 Low fix success rate. Focus on improving fix quality over quantity."
            )

        if successful_fixes > 0 and total_tokens / successful_fixes > 200:
            recommendations.append(
                "🪙 High token usage per fix. Consider optimizing prompts and context."
            )

        if efficiency_score >= 0.7:
            recommendations.append("🎉 Great efficiency! Keep up the excellent work.")

        if not recommendations:
            recommendations.append(
                "📊 Moderate efficiency. Look for opportunities to optimize token usage and fix accuracy."
            )

        return recommendations
