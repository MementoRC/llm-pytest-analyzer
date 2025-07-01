import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pytest_analyzer.core.domain.entities.pytest_failure import PytestFailure


class EfficiencyTracker:
    """
    Tracks and analyzes efficiency metrics related to test failures, LLM usage,
    and autofix attempts across different sessions.

    It uses an SQLite database to persist session data and provides methods
    to record events, calculate an efficiency score, and generate recommendations.
    """

    def __init__(self, db_path: str = ":memory:"):
        """
        Initializes the EfficiencyTracker.

        Args:
            db_path: Path to the SQLite database file. Use ':memory:' for an in-memory database.
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._cursor: Optional[sqlite3.Cursor] = None
        self._lock = threading.Lock()
        self._current_session_id: Optional[str] = None
        self._initialize_db()

    def _initialize_db(self):
        """Initializes the SQLite database schema."""
        with self._lock:
            if self._conn:
                self._conn.close()  # Close existing connection if any
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._cursor = self._conn.cursor()
            self._cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_failures INTEGER DEFAULT 0,
                    total_llm_prompt_tokens INTEGER DEFAULT 0,
                    total_llm_completion_tokens INTEGER DEFAULT 0,
                    autofix_attempts INTEGER DEFAULT 0,
                    autofix_successes INTEGER DEFAULT 0,
                    efficiency_score REAL DEFAULT 0.0,
                    recommendations TEXT
                )
            """)
            self._cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_token_usage (
                    session_id TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)
            self._cursor.execute("""
                CREATE TABLE IF NOT EXISTS autofix_attempts (
                    session_id TEXT NOT NULL,
                    failure_id TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)
            self._cursor.execute("""
                CREATE TABLE IF NOT EXISTS failures (
                    session_id TEXT NOT NULL,
                    failure_id TEXT PRIMARY KEY,
                    test_name TEXT NOT NULL,
                    file_path TEXT,
                    failure_message TEXT,
                    error_type TEXT,
                    line_number INTEGER,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)
            self._conn.commit()

    def start_session(self):
        """
        Starts a new tracking session.

        Raises:
            RuntimeError: If a session is already active.
        """
        with self._lock:
            if self._current_session_id:
                raise RuntimeError(
                    "A session is already active. Call end_session() first."
                )
            self._current_session_id = str(uuid4())
            start_time = datetime.now().isoformat()
            self._cursor.execute(
                "INSERT INTO sessions (id, start_time) VALUES (?, ?)",
                (self._current_session_id, start_time),
            )
            self._conn.commit()

    def end_session(self):
        """
        Ends the current tracking session, calculates metrics, and stores the summary.

        Raises:
            RuntimeError: If no session is active.
        """
        with self._lock:
            if not self._current_session_id:
                raise RuntimeError(
                    "No active session to end. Call start_session() first."
                )

            end_time = datetime.now().isoformat()
            session_id = self._current_session_id

            # Calculate aggregates for the current session
            self._cursor.execute(
                "SELECT SUM(prompt_tokens), SUM(completion_tokens) FROM llm_token_usage WHERE session_id = ?",
                (session_id,),
            )
            llm_tokens = self._cursor.fetchone()
            total_prompt_tokens = (
                llm_tokens[0] if llm_tokens and llm_tokens[0] is not None else 0
            )
            total_completion_tokens = (
                llm_tokens[1] if llm_tokens and llm_tokens[1] is not None else 0
            )

            self._cursor.execute(
                "SELECT COUNT(*), SUM(success) FROM autofix_attempts WHERE session_id = ?",
                (session_id,),
            )
            autofix_data = self._cursor.fetchone()
            autofix_attempts = (
                autofix_data[0] if autofix_data and autofix_data[0] is not None else 0
            )
            autofix_successes = (
                autofix_data[1] if autofix_data and autofix_data[1] is not None else 0
            )

            self._cursor.execute(
                "SELECT COUNT(*) FROM failures WHERE session_id = ?", (session_id,)
            )
            total_failures = self._cursor.fetchone()[0]

            # Calculate efficiency score and recommendations
            efficiency_score = self._calculate_efficiency_score(
                total_failures,
                total_prompt_tokens + total_completion_tokens,
                autofix_successes,
                autofix_attempts,
            )
            recommendations = self._generate_recommendations(
                total_failures,
                total_prompt_tokens + total_completion_tokens,
                autofix_successes,
                autofix_attempts,
            )

            self._cursor.execute(
                """
                UPDATE sessions
                SET end_time = ?,
                    total_failures = ?,
                    total_llm_prompt_tokens = ?,
                    total_llm_completion_tokens = ?,
                    autofix_attempts = ?,
                    autofix_successes = ?,
                    efficiency_score = ?,
                    recommendations = ?
                WHERE id = ?
                """,
                (
                    end_time,
                    total_failures,
                    total_prompt_tokens,
                    total_completion_tokens,
                    autofix_attempts,
                    autofix_successes,
                    efficiency_score,
                    recommendations,
                    session_id,
                ),
            )
            self._conn.commit()
            self._current_session_id = None  # Reset for next session

    def record_llm_tokens(self, prompt_tokens: int, completion_tokens: int):
        """
        Records LLM token usage for the current session.

        Args:
            prompt_tokens: Number of tokens used for the prompt.
            completion_tokens: Number of tokens generated in the completion.

        Raises:
            RuntimeError: If no session is active.
            ValueError: If token counts are negative.
        """
        with self._lock:
            if not self._current_session_id:
                raise RuntimeError("No active session. Call start_session() first.")
            if prompt_tokens < 0 or completion_tokens < 0:
                raise ValueError("Token counts cannot be negative.")
            self._cursor.execute(
                "INSERT INTO llm_token_usage (session_id, prompt_tokens, completion_tokens, timestamp) VALUES (?, ?, ?, ?)",
                (
                    self._current_session_id,
                    prompt_tokens,
                    completion_tokens,
                    datetime.now().isoformat(),
                ),
            )
            self._conn.commit()

    def record_autofix_attempt(self, failure_id: str, success: bool):
        """
        Records an autofix attempt and its outcome for the current session.

        Args:
            failure_id: The ID of the PytestFailure associated with the autofix attempt.
            success: True if the autofix was successful, False otherwise.

        Raises:
            RuntimeError: If no session is active.
        """
        with self._lock:
            if not self._current_session_id:
                raise RuntimeError("No active session. Call start_session() first.")
            self._cursor.execute(
                "INSERT INTO autofix_attempts (session_id, failure_id, success, timestamp) VALUES (?, ?, ?, ?)",
                (
                    self._current_session_id,
                    failure_id,
                    int(success),
                    datetime.now().isoformat(),
                ),
            )
            self._conn.commit()

    def record_failure(self, failure: PytestFailure):
        """
        Records a test failure for the current session.

        Args:
            failure: The PytestFailure object to record.

        Raises:
            RuntimeError: If no session is active.
        """
        with self._lock:
            if not self._current_session_id:
                raise RuntimeError("No active session. Call start_session() first.")
            self._cursor.execute(
                "INSERT INTO failures (session_id, failure_id, test_name, file_path, failure_message, error_type, line_number, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self._current_session_id,
                    failure.id,
                    failure.test_name,
                    failure.file_path,
                    failure.failure_message,
                    failure.error_type,
                    failure.line_number,
                    datetime.now().isoformat(),
                ),
            )
            self._conn.commit()

    def _calculate_efficiency_score(
        self,
        total_failures: int,
        total_llm_tokens: int,
        autofix_successes: int,
        autofix_attempts: int,
    ) -> float:
        """
        Calculates an efficiency score based on session metrics.

        A higher score indicates better efficiency.
        Score is normalized between 0 and 100.
        """
        score = 100.0  # Base score

        # Deductions for negative impacts
        score -= total_failures * 5  # Arbitrary deduction per failure
        score -= (
            total_llm_tokens * 0.0005
        )  # Arbitrary deduction per token (e.g., 0.5 points per 1000 tokens)

        # Bonuses for positive impacts
        if autofix_attempts > 0:
            autofix_success_rate = autofix_successes / autofix_attempts
            score += autofix_success_rate * 20  # Bonus for successful autofixes

        return max(0.0, min(100.0, score))  # Clamp score between 0 and 100

    def _generate_recommendations(
        self,
        total_failures: int,
        total_llm_tokens: int,
        autofix_successes: int,
        autofix_attempts: int,
    ) -> str:
        """
        Generates recommendations based on session metrics.
        """
        recommendations = []

        if total_failures > 10:
            recommendations.append(
                "High number of test failures. Prioritize fixing flaky or broken tests."
            )
        elif total_failures > 0:
            recommendations.append(
                "Monitor test failures closely and address them promptly."
            )

        if total_llm_tokens > 50000:
            recommendations.append(
                "Very high LLM token usage. Investigate opportunities to reduce prompt size, cache responses, or refine LLM calls."
            )
        elif total_llm_tokens > 10000:
            recommendations.append(
                "High LLM token usage. Consider optimizing LLM interactions to manage costs."
            )

        if autofix_attempts > 0:
            autofix_success_rate = autofix_successes / autofix_attempts
            if autofix_success_rate < 0.3:
                recommendations.append(
                    "Very low autofix success rate. Review autofix logic and ensure it's effective."
                )
            elif autofix_success_rate < 0.6:
                recommendations.append(
                    "Moderate autofix success rate. Look for ways to improve autofix reliability."
                )
            elif autofix_success_rate >= 0.8:
                recommendations.append(
                    "Autofix is performing well. Continue leveraging this capability."
                )
        elif total_failures > 0:
            recommendations.append(
                "No autofix attempts recorded for failures. Consider enabling or improving autofix capabilities to reduce manual effort."
            )

        if not recommendations:
            recommendations.append(
                "System is performing efficiently. No specific recommendations at this time."
            )

        return "\n".join(recommendations)

    def get_session_summary(
        self, session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the summary of a specific session or the current active session.

        Args:
            session_id: The ID of the session to retrieve. If None, returns the current active session.

        Returns:
            A dictionary containing the session summary, or None if not found.
        """
        with self._lock:
            target_session_id = session_id if session_id else self._current_session_id
            if not target_session_id:
                return None

            self._cursor.execute(
                "SELECT * FROM sessions WHERE id = ?", (target_session_id,)
            )
            row = self._cursor.fetchone()
            if row:
                columns = [description[0] for description in self._cursor.description]
                summary = dict(zip(columns, row))
                # Convert recommendations string back to list if needed, or keep as string
                return summary
            return None

    def get_all_sessions_summary(self) -> List[Dict[str, Any]]:
        """
        Retrieves summaries for all recorded sessions, ordered by start time (most recent first).

        Returns:
            A list of dictionaries, each representing a session summary.
        """
        with self._lock:
            self._cursor.execute("SELECT * FROM sessions ORDER BY start_time DESC")
            rows = self._cursor.fetchall()
            columns = [description[0] for description in self._cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    def reset(self):
        """
        Clears all data from the database and resets the tracker to its initial state.
        This effectively starts a fresh database.
        """
        with self._lock:
            if self._conn:
                self._conn.close()
            self._conn = None
            self._cursor = None
            self._current_session_id = None
            self._initialize_db()

    def close(self):
        """Closes the database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                self._cursor = None

    def __del__(self):
        """Ensures the database connection is closed when the object is garbage collected."""
        self.close()
