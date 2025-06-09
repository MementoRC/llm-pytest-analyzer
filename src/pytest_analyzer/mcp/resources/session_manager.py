"""Session management for MCP resources.

Manages analysis sessions for storing and retrieving test results, suggestions, and history.
"""

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional

from ..schemas import FixSuggestionData, PytestFailureData


@dataclass
class AnalysisSession:
    """Represents an analysis session with test results and suggestions."""

    id: str
    created_at: float
    updated_at: float
    test_results: List[PytestFailureData] = field(default_factory=list)
    suggestions: List[FixSuggestionData] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_timestamp(self) -> None:
        """Update the session's last updated timestamp."""
        self.updated_at = time.time()

    def add_test_results(self, results: List[PytestFailureData]) -> None:
        """Add test results to the session."""
        self.test_results.extend(results)
        self.update_timestamp()

    def add_suggestions(self, suggestions: List[FixSuggestionData]) -> None:
        """Add fix suggestions to the session."""
        self.suggestions.extend(suggestions)
        self.update_timestamp()

    def filter_test_results(self, filters: Dict[str, Any]) -> List[PytestFailureData]:
        """Filter test results based on provided criteria."""
        results = self.test_results

        # Filter by status
        if "status" in filters:
            status = filters["status"]
            # For now, we assume all failures have status "failed"
            # This could be extended with actual status tracking
            if status != "failed":
                results = []

        # Filter by failure type
        if "type" in filters:
            failure_type = filters["type"]
            results = [r for r in results if r.failure_type == failure_type]

        # Filter by file
        if "file" in filters:
            file_pattern = filters["file"]
            results = [r for r in results if file_pattern in r.file_path]

        return results

    def filter_suggestions(self, filters: Dict[str, Any]) -> List[FixSuggestionData]:
        """Filter suggestions based on provided criteria."""
        suggestions = self.suggestions

        # Filter by confidence level
        if "min_confidence" in filters:
            min_conf = float(filters["min_confidence"])
            suggestions = [s for s in suggestions if s.confidence_score >= min_conf]

        # Filter by failure ID
        if "failure_id" in filters:
            failure_id = filters["failure_id"]
            suggestions = [s for s in suggestions if s.failure_id == failure_id]

        return suggestions

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization."""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "test_results_count": len(self.test_results),
            "suggestions_count": len(self.suggestions),
            "metadata": self.metadata,
        }


class SessionManager:
    """Manages analysis sessions with TTL-based cleanup."""

    def __init__(self, ttl_seconds: int = 300, max_sessions: int = 100):
        """Initialize session manager.

        Args:
            ttl_seconds: Time-to-live for sessions in seconds
            max_sessions: Maximum number of sessions to keep
        """
        self._sessions: Dict[str, AnalysisSession] = {}
        self._ttl_seconds = ttl_seconds
        self._max_sessions = max_sessions
        self._lock = Lock()

    def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new analysis session.

        Args:
            metadata: Optional metadata for the session

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        current_time = time.time()

        session = AnalysisSession(
            id=session_id,
            created_at=current_time,
            updated_at=current_time,
            metadata=metadata or {},
        )

        with self._lock:
            self._cleanup_expired_sessions()
            self._sessions[session_id] = session

        return session_id

    def get_session(self, session_id: str) -> Optional[AnalysisSession]:
        """Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session if found and not expired, None otherwise
        """
        with self._lock:
            self._cleanup_expired_sessions()
            return self._sessions.get(session_id)

    def store_test_results(
        self, session_id: str, results: List[PytestFailureData]
    ) -> bool:
        """Store test results in a session.

        Args:
            session_id: Session identifier
            results: List of test failure data

        Returns:
            True if stored successfully, False if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return False

        session.add_test_results(results)
        return True

    def store_suggestions(
        self, session_id: str, suggestions: List[FixSuggestionData]
    ) -> bool:
        """Store fix suggestions in a session.

        Args:
            session_id: Session identifier
            suggestions: List of fix suggestions

        Returns:
            True if stored successfully, False if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return False

        session.add_suggestions(suggestions)
        return True

    def get_recent_sessions(self, limit: int = 10) -> List[AnalysisSession]:
        """Get recent sessions sorted by update time.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of recent sessions
        """
        with self._lock:
            self._cleanup_expired_sessions()
            sessions = list(self._sessions.values())

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    def get_session_count(self) -> int:
        """Get current number of active sessions."""
        with self._lock:
            self._cleanup_expired_sessions()
            return len(self._sessions)

    def clear_expired_sessions(self) -> int:
        """Manually clear expired sessions.

        Returns:
            Number of sessions removed
        """
        with self._lock:
            return self._cleanup_expired_sessions()

    def _cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (internal method).

        Returns:
            Number of sessions removed
        """
        current_time = time.time()
        expired_sessions = []

        for session_id, session in self._sessions.items():
            if current_time - session.updated_at > self._ttl_seconds:
                expired_sessions.append(session_id)

        # Remove expired sessions
        for session_id in expired_sessions:
            del self._sessions[session_id]

        # If still over limit, remove oldest sessions
        if len(self._sessions) > self._max_sessions:
            sessions_by_age = sorted(
                self._sessions.items(), key=lambda x: x[1].updated_at
            )
            excess_count = len(self._sessions) - self._max_sessions

            for i in range(excess_count):
                session_id = sessions_by_age[i][0]
                del self._sessions[session_id]
                expired_sessions.append(session_id)

        return len(expired_sessions)

    def cleanup_all_sessions(self) -> None:
        """Remove all sessions (for testing/reset purposes)."""
        with self._lock:
            self._sessions.clear()


__all__ = ["AnalysisSession", "SessionManager"]
