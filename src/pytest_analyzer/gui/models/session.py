"""
Session management models for the Pytest Analyzer GUI.

This module contains the Session class and related functionality for saving
and restoring analysis sessions, including test results, analysis data, and bookmarks.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from .test_results_model import AnalysisStatus, TestResult, TestStatus

logger = logging.getLogger(__name__)


@dataclass
class SessionBookmark:
    """Represents a bookmarked test failure or result."""

    test_name: str
    bookmark_type: str  # 'failure', 'important', 'fixed', 'investigating'
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "test_name": self.test_name,
            "bookmark_type": self.bookmark_type,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionBookmark":
        """Create from dictionary."""
        return cls(
            test_name=data["test_name"],
            bookmark_type=data["bookmark_type"],
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            tags=data.get("tags", []),
            notes=data.get("notes", ""),
        )


@dataclass
class AnalysisHistoryEntry:
    """Represents an entry in the analysis history."""

    timestamp: datetime
    test_name: str
    analysis_type: str  # 'initial', 'reanalysis', 'manual'
    suggestions_count: int
    status: str  # 'success', 'failed', 'partial'
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "test_name": self.test_name,
            "analysis_type": self.analysis_type,
            "suggestions_count": self.suggestions_count,
            "status": self.status,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisHistoryEntry":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            test_name=data["test_name"],
            analysis_type=data["analysis_type"],
            suggestions_count=data["suggestions_count"],
            status=data["status"],
            details=data.get("details", {}),
        )


@dataclass
class SessionMetadata:
    """Metadata for a session."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_modified: datetime = field(default_factory=datetime.now)
    project_path: Optional[Path] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat(),
            "project_path": str(self.project_path) if self.project_path else None,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMetadata":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_modified=datetime.fromisoformat(data["last_modified"]),
            project_path=Path(data["project_path"]) if data.get("project_path") else None,
            tags=data.get("tags", []),
        )


@dataclass
class SessionData:
    """Main session data container."""

    metadata: SessionMetadata
    test_results: List[TestResult] = field(default_factory=list)
    bookmarks: List[SessionBookmark] = field(default_factory=list)
    analysis_history: List[AnalysisHistoryEntry] = field(default_factory=list)
    workflow_state: str = "idle"
    custom_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metadata": self.metadata.to_dict(),
            "test_results": [self._test_result_to_dict(tr) for tr in self.test_results],
            "bookmarks": [bm.to_dict() for bm in self.bookmarks],
            "analysis_history": [ah.to_dict() for ah in self.analysis_history],
            "workflow_state": self.workflow_state,
            "custom_data": self.custom_data,
            "version": "1.0",  # For future compatibility
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Create from dictionary."""
        metadata = SessionMetadata.from_dict(data["metadata"])

        # Reconstruct test results
        test_results = []
        for tr_data in data.get("test_results", []):
            test_results.append(cls._test_result_from_dict(tr_data))

        # Reconstruct bookmarks
        bookmarks = []
        for bm_data in data.get("bookmarks", []):
            bookmarks.append(SessionBookmark.from_dict(bm_data))

        # Reconstruct analysis history
        analysis_history = []
        for ah_data in data.get("analysis_history", []):
            analysis_history.append(AnalysisHistoryEntry.from_dict(ah_data))

        return cls(
            metadata=metadata,
            test_results=test_results,
            bookmarks=bookmarks,
            analysis_history=analysis_history,
            workflow_state=data.get("workflow_state", "idle"),
            custom_data=data.get("custom_data", {}),
        )

    def _test_result_to_dict(self, test_result: TestResult) -> Dict[str, Any]:
        """Convert TestResult to dictionary."""
        return {
            "name": test_result.name,
            "status": test_result.status.name,
            "duration": test_result.duration,
            "file_path": str(test_result.file_path) if test_result.file_path else None,
            "failure_details": asdict(test_result.failure_details)
            if test_result.failure_details
            else None,
            "suggestions": [asdict(s) for s in test_result.suggestions],
            "analysis_status": test_result.analysis_status.name,
        }

    @classmethod
    def _test_result_from_dict(cls, data: Dict[str, Any]) -> TestResult:
        """Create TestResult from dictionary."""
        from ...core.models.failure_analysis import FixSuggestion
        from .test_results_model import TestFailureDetails

        # Reconstruct failure details
        failure_details = None
        if data.get("failure_details"):
            failure_details = TestFailureDetails(**data["failure_details"])

        # Reconstruct suggestions
        suggestions = []
        for s_data in data.get("suggestions", []):
            suggestions.append(FixSuggestion(**s_data))

        return TestResult(
            name=data["name"],
            status=TestStatus[data["status"]],
            duration=data.get("duration", 0.0),
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            failure_details=failure_details,
            suggestions=suggestions,
            analysis_status=AnalysisStatus[data["analysis_status"]],
        )


class SessionManager(QObject):
    """Manages session operations including save, load, and history."""

    session_saved = Signal(str)  # session_id
    session_loaded = Signal(SessionData)
    session_deleted = Signal(str)  # session_id
    bookmark_added = Signal(SessionBookmark)
    bookmark_removed = Signal(str)  # test_name

    def __init__(self, sessions_dir: Optional[Path] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.sessions_dir = sessions_dir or Path.home() / ".pytest-analyzer" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self._current_session: Optional[SessionData] = None
        self._auto_save_enabled = True

    @property
    def current_session(self) -> Optional[SessionData]:
        """Get the current session."""
        return self._current_session

    def create_new_session(
        self, name: str = "", description: str = "", project_path: Optional[Path] = None
    ) -> SessionData:
        """Create a new session."""
        metadata = SessionMetadata(
            name=name or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            description=description,
            project_path=project_path,
        )

        session = SessionData(metadata=metadata)
        self._current_session = session

        if self._auto_save_enabled:
            self.save_session(session)

        logger.info(f"Created new session: {session.metadata.name}")
        return session

    def save_session(self, session: Optional[SessionData] = None) -> bool:
        """Save a session to disk."""
        if session is None:
            session = self._current_session

        if session is None:
            logger.warning("No session to save")
            return False

        try:
            # Update last modified timestamp
            session.metadata.last_modified = datetime.now()

            # Save to file
            session_file = self.sessions_dir / f"{session.metadata.id}.json"
            session_data = session.to_dict()

            session_file.write_text(json.dumps(session_data, indent=2))

            self.session_saved.emit(session.metadata.id)
            logger.info(f"Saved session: {session.metadata.name} to {session_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False

    def load_session(self, session_id: str) -> Optional[SessionData]:
        """Load a session from disk."""
        try:
            session_file = self.sessions_dir / f"{session_id}.json"

            if not session_file.exists():
                logger.error(f"Session file not found: {session_file}")
                return None

            session_data = json.loads(session_file.read_text())
            session = SessionData.from_dict(session_data)

            self._current_session = session
            self.session_loaded.emit(session)

            logger.info(f"Loaded session: {session.metadata.name}")
            return session

        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def list_sessions(self) -> List[SessionMetadata]:
        """List all available sessions."""
        sessions = []

        try:
            for session_file in self.sessions_dir.glob("*.json"):
                try:
                    session_data = json.loads(session_file.read_text())
                    metadata = SessionMetadata.from_dict(session_data["metadata"])
                    sessions.append(metadata)
                except Exception as e:
                    logger.warning(f"Failed to read session metadata from {session_file}: {e}")

            # Sort by last modified (newest first)
            sessions.sort(key=lambda s: s.last_modified, reverse=True)

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")

        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        try:
            session_file = self.sessions_dir / f"{session_id}.json"

            if session_file.exists():
                session_file.unlink()
                self.session_deleted.emit(session_id)
                logger.info(f"Deleted session: {session_id}")
                return True
            logger.warning(f"Session file not found for deletion: {session_id}")
            return False

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    def export_session(self, session: SessionData, export_path: Path) -> bool:
        """Export a session to a file."""
        try:
            session_data = session.to_dict()
            export_path.write_text(json.dumps(session_data, indent=2))
            logger.info(f"Exported session to: {export_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export session: {e}")
            return False

    def import_session(self, import_path: Path) -> Optional[SessionData]:
        """Import a session from a file."""
        try:
            session_data = json.loads(import_path.read_text())
            session = SessionData.from_dict(session_data)

            # Generate new ID to avoid conflicts
            session.metadata.id = str(uuid4())
            session.metadata.name += " (Imported)"

            # Save the imported session
            if self.save_session(session):
                return session
            return None

        except Exception as e:
            logger.error(f"Failed to import session from {import_path}: {e}")
            return None

    def add_bookmark(
        self,
        test_name: str,
        bookmark_type: str = "important",
        description: str = "",
        notes: str = "",
        tags: List[str] = None,
    ) -> SessionBookmark:
        """Add a bookmark to the current session."""
        if self._current_session is None:
            raise ValueError("No active session to add bookmark to")

        bookmark = SessionBookmark(
            test_name=test_name,
            bookmark_type=bookmark_type,
            description=description,
            notes=notes,
            tags=tags or [],
        )

        # Remove existing bookmark for the same test if it exists
        self._current_session.bookmarks = [
            b for b in self._current_session.bookmarks if b.test_name != test_name
        ]

        self._current_session.bookmarks.append(bookmark)

        if self._auto_save_enabled:
            self.save_session()

        self.bookmark_added.emit(bookmark)
        logger.info(f"Added bookmark for test: {test_name}")
        return bookmark

    def remove_bookmark(self, test_name: str) -> bool:
        """Remove a bookmark from the current session."""
        if self._current_session is None:
            return False

        original_count = len(self._current_session.bookmarks)
        self._current_session.bookmarks = [
            b for b in self._current_session.bookmarks if b.test_name != test_name
        ]

        removed = len(self._current_session.bookmarks) < original_count

        if removed:
            if self._auto_save_enabled:
                self.save_session()
            self.bookmark_removed.emit(test_name)
            logger.info(f"Removed bookmark for test: {test_name}")

        return removed

    def add_analysis_history_entry(
        self,
        test_name: str,
        analysis_type: str,
        suggestions_count: int,
        status: str,
        details: Dict[str, Any] = None,
    ) -> AnalysisHistoryEntry:
        """Add an entry to the analysis history."""
        if self._current_session is None:
            raise ValueError("No active session to add analysis history to")

        entry = AnalysisHistoryEntry(
            timestamp=datetime.now(),
            test_name=test_name,
            analysis_type=analysis_type,
            suggestions_count=suggestions_count,
            status=status,
            details=details or {},
        )

        self._current_session.analysis_history.append(entry)

        if self._auto_save_enabled:
            self.save_session()

        logger.debug(f"Added analysis history entry for test: {test_name}")
        return entry

    def get_bookmarks_for_test(self, test_name: str) -> List[SessionBookmark]:
        """Get all bookmarks for a specific test."""
        if self._current_session is None:
            return []

        return [b for b in self._current_session.bookmarks if b.test_name == test_name]

    def get_analysis_history_for_test(self, test_name: str) -> List[AnalysisHistoryEntry]:
        """Get analysis history for a specific test."""
        if self._current_session is None:
            return []

        return [e for e in self._current_session.analysis_history if e.test_name == test_name]

    def set_auto_save(self, enabled: bool) -> None:
        """Enable or disable automatic saving."""
        self._auto_save_enabled = enabled
        logger.info(f"Auto-save {'enabled' if enabled else 'disabled'}")

    def update_session_metadata(
        self, name: str = None, description: str = None, tags: List[str] = None
    ) -> bool:
        """Update current session metadata."""
        if self._current_session is None:
            return False

        if name is not None:
            self._current_session.metadata.name = name
        if description is not None:
            self._current_session.metadata.description = description
        if tags is not None:
            self._current_session.metadata.tags = tags

        self._current_session.metadata.last_modified = datetime.now()

        if self._auto_save_enabled:
            self.save_session()

        return True
