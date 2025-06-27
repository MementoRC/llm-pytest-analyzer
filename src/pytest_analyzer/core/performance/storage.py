"""
Storage backend for performance benchmark data.

This module provides persistent storage for benchmark results and historical data.
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

from .metrics import BenchmarkResult, BenchmarkSuite, MetricType


class BenchmarkStorage:
    """Persistent storage for benchmark results using SQLite."""

    def __init__(self, db_path: Union[str, Path]):
        """Initialize storage with database path."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS benchmark_suites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        tests TEXT,  -- JSON array
                        thresholds TEXT,  -- JSON object
                        created_at TEXT,
                        tags TEXT  -- JSON array
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS benchmark_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        benchmark_id TEXT NOT NULL,
                        suite_name TEXT NOT NULL,
                        test_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        duration REAL NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        error_message TEXT,
                        environment TEXT,  -- JSON object
                        metadata TEXT  -- JSON object
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS benchmark_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        result_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        value REAL NOT NULL,
                        unit TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        context TEXT,  -- JSON object
                        FOREIGN KEY (result_id) REFERENCES benchmark_results (id)
                    )
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_results_suite_test
                    ON benchmark_results (suite_name, test_name)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_results_start_time
                    ON benchmark_results (start_time)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_name_type
                    ON benchmark_metrics (name, metric_type)
                """)

    def store_suite(self, suite: BenchmarkSuite) -> int:
        """Store a benchmark suite."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO benchmark_suites
                    (name, description, tests, thresholds, created_at, tags)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        suite.name,
                        suite.description,
                        json.dumps(suite.tests),
                        json.dumps(suite.thresholds),
                        suite.created_at.isoformat(),
                        json.dumps(suite.tags),
                    ),
                )
                return cursor.lastrowid

    def load_suite(self, name: str) -> Optional[BenchmarkSuite]:
        """Load a benchmark suite by name."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT name, description, tests, thresholds, created_at, tags
                    FROM benchmark_suites WHERE name = ?
                """,
                    (name,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                return BenchmarkSuite(
                    name=row[0],
                    description=row[1],
                    tests=json.loads(row[2]),
                    thresholds=json.loads(row[3]),
                    created_at=datetime.fromisoformat(row[4]),
                    tags=json.loads(row[5]),
                )

    def list_suites(self) -> List[str]:
        """List all available benchmark suites."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM benchmark_suites ORDER BY name")
                return [row[0] for row in cursor.fetchall()]

    def store_result(self, result: BenchmarkResult) -> int:
        """Store a benchmark result."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Store the main result
                cursor.execute(
                    """
                    INSERT INTO benchmark_results
                    (benchmark_id, suite_name, test_name, status, duration,
                     start_time, end_time, error_message, environment, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        result.benchmark_id,
                        result.suite_name,
                        result.test_name,
                        result.status.name,
                        result.duration,
                        result.start_time.isoformat(),
                        result.end_time.isoformat() if result.end_time else None,
                        result.error_message,
                        json.dumps(result.environment),
                        json.dumps(result.metadata),
                    ),
                )

                result_id = cursor.lastrowid

                # Store the metrics
                for metric in result.metrics:
                    cursor.execute(
                        """
                        INSERT INTO benchmark_metrics
                        (result_id, name, value, unit, metric_type, timestamp, context)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            result_id,
                            metric.name,
                            metric.value,
                            metric.unit,
                            metric.metric_type.name,
                            metric.timestamp.isoformat(),
                            json.dumps(metric.context),
                        ),
                    )

                return result_id

    def load_result(self, result_id: int) -> Optional[BenchmarkResult]:
        """Load a benchmark result by ID."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Load the main result
                cursor.execute(
                    """
                    SELECT benchmark_id, suite_name, test_name, status, duration,
                           start_time, end_time, error_message, environment, metadata
                    FROM benchmark_results WHERE id = ?
                """,
                    (result_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                # Load the metrics
                cursor.execute(
                    """
                    SELECT name, value, unit, metric_type, timestamp, context
                    FROM benchmark_metrics WHERE result_id = ?
                """,
                    (result_id,),
                )

                from .metrics import BenchmarkMetric, BenchmarkStatus

                metrics = []
                for metric_row in cursor.fetchall():
                    metrics.append(
                        BenchmarkMetric(
                            name=metric_row[0],
                            value=metric_row[1],
                            unit=metric_row[2],
                            metric_type=MetricType[metric_row[3]],
                            timestamp=datetime.fromisoformat(metric_row[4]),
                            context=json.loads(metric_row[5]),
                        )
                    )

                return BenchmarkResult(
                    benchmark_id=row[0],
                    suite_name=row[1],
                    test_name=row[2],
                    metrics=metrics,
                    status=BenchmarkStatus[row[3]],
                    duration=row[4],
                    start_time=datetime.fromisoformat(row[5]),
                    end_time=datetime.fromisoformat(row[6]) if row[6] else None,
                    error_message=row[7],
                    environment=json.loads(row[8]),
                    metadata=json.loads(row[9]),
                )

    def get_recent_results(
        self,
        suite_name: str,
        test_name: Optional[str] = None,
        limit: int = 100,
        days: int = 30,
    ) -> List[BenchmarkResult]:
        """Get recent benchmark results for a suite/test."""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if test_name:
                    cursor.execute(
                        """
                        SELECT id FROM benchmark_results
                        WHERE suite_name = ? AND test_name = ? AND start_time >= ?
                        ORDER BY start_time DESC LIMIT ?
                    """,
                        (suite_name, test_name, cutoff_date.isoformat(), limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT id FROM benchmark_results
                        WHERE suite_name = ? AND start_time >= ?
                        ORDER BY start_time DESC LIMIT ?
                    """,
                        (suite_name, cutoff_date.isoformat(), limit),
                    )

                result_ids = [row[0] for row in cursor.fetchall()]

        return [self.load_result(result_id) for result_id in result_ids if result_id]

    def get_baseline_result(
        self, suite_name: str, test_name: str
    ) -> Optional[BenchmarkResult]:
        """Get the baseline result for a test (most recent successful result)."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id FROM benchmark_results
                    WHERE suite_name = ? AND test_name = ? AND status = 'COMPLETED'
                    ORDER BY start_time DESC LIMIT 1
                """,
                    (suite_name, test_name),
                )

                row = cursor.fetchone()
                if row:
                    return self.load_result(row[0])

        return None

    def get_metric_history(
        self, suite_name: str, test_name: str, metric_name: str, days: int = 30
    ) -> List[Dict[str, Union[datetime, float]]]:
        """Get historical values for a specific metric."""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT m.value, m.timestamp, r.start_time
                    FROM benchmark_metrics m
                    JOIN benchmark_results r ON m.result_id = r.id
                    WHERE r.suite_name = ? AND r.test_name = ? AND m.name = ?
                          AND r.start_time >= ? AND r.status = 'COMPLETED'
                    ORDER BY r.start_time ASC
                """,
                    (suite_name, test_name, metric_name, cutoff_date.isoformat()),
                )

                return [
                    {
                        "value": row[0],
                        "timestamp": datetime.fromisoformat(row[1]),
                        "run_time": datetime.fromisoformat(row[2]),
                    }
                    for row in cursor.fetchall()
                ]

    def cleanup_old_results(self, days: int = 90):
        """Remove benchmark results older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get old result IDs
                cursor.execute(
                    """
                    SELECT id FROM benchmark_results WHERE start_time < ?
                """,
                    (cutoff_date.isoformat(),),
                )
                old_result_ids = [row[0] for row in cursor.fetchall()]

                if old_result_ids:
                    # Delete metrics for old results
                    placeholders = ",".join("?" * len(old_result_ids))
                    cursor.execute(
                        f"""
                        DELETE FROM benchmark_metrics WHERE result_id IN ({placeholders})
                    """,
                        old_result_ids,
                    )

                    # Delete old results
                    cursor.execute(
                        """
                        DELETE FROM benchmark_results WHERE start_time < ?
                    """,
                        (cutoff_date.isoformat(),),
                    )

                return len(old_result_ids)

    def get_summary_stats(self, suite_name: str) -> Dict[str, int]:
        """Get summary statistics for a benchmark suite."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Total results
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM benchmark_results WHERE suite_name = ?
                """,
                    (suite_name,),
                )
                total_results = cursor.fetchone()[0]

                # Results by status
                cursor.execute(
                    """
                    SELECT status, COUNT(*) FROM benchmark_results
                    WHERE suite_name = ? GROUP BY status
                """,
                    (suite_name,),
                )
                status_counts = dict(cursor.fetchall())

                # Recent results (last 7 days)
                week_ago = datetime.now() - timedelta(days=7)
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM benchmark_results
                    WHERE suite_name = ? AND start_time >= ?
                """,
                    (suite_name, week_ago.isoformat()),
                )
                recent_results = cursor.fetchone()[0]

                return {
                    "total_results": total_results,
                    "recent_results": recent_results,
                    **status_counts,
                }
