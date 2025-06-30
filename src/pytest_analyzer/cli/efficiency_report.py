#!/usr/bin/env python3

"""
Efficiency Report CLI Command

Provides efficiency reporting and analysis for pytest-analyzer.
"""

import argparse
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..metrics.efficiency_tracker import EfficiencyTracker
from ..utils.settings import Settings, load_settings

# Create logger
logger = logging.getLogger("pytest_analyzer.efficiency_report")

# Setup rich console
console = Console()


class EfficiencyReportCommand:
    """Command to generate efficiency reports and analysis."""

    def __init__(
        self,
        efficiency_tracker: Optional[EfficiencyTracker] = None,
        settings: Optional[Settings] = None,
    ):
        """Initialize the command with required components."""
        self.efficiency_tracker = efficiency_tracker
        self._initial_settings = settings

    def parse_arguments(self) -> argparse.Namespace:
        """Parse command line arguments for the efficiency-report command."""
        parser = argparse.ArgumentParser(
            prog="pytest-analyzer efficiency-report",
            description="""
Generate efficiency reports and analysis for test/fix sessions, including trends and recommendations.

[bold]Examples:[/bold]
  pytest-analyzer efficiency-report --time-range week
  pytest-analyzer efficiency-report --compare --trends
  pytest-analyzer efficiency-report --format json --output-file eff.json
""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        # Time range options
        time_group = parser.add_argument_group("Time Range Options")
        time_group.add_argument(
            "--time-range",
            choices=["day", "week", "month", "all"],
            default="week",
            help="Time range for the report (default: week)",
        )
        time_group.add_argument(
            "--start-date",
            type=str,
            help="Start date for custom range (YYYY-MM-DD format)",
        )
        time_group.add_argument(
            "--end-date",
            type=str,
            help="End date for custom range (YYYY-MM-DD format)",
        )

        # Output format options
        output_group = parser.add_argument_group("Output Options")
        output_group.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Output format (default: table)",
        )
        output_group.add_argument(
            "--output-file",
            type=str,
            help="Save report to specified file",
        )
        output_group.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Enable verbose output with detailed metrics",
        )

        # Analysis options
        analysis_group = parser.add_argument_group("Analysis Options")
        analysis_group.add_argument(
            "--compare",
            action="store_true",
            help="Include comparative analysis with previous period",
        )
        analysis_group.add_argument(
            "--trends",
            action="store_true",
            help="Include trend analysis and visualizations",
        )
        analysis_group.add_argument(
            "--recommendations",
            action="store_true",
            help="Include efficiency recommendations",
        )

        # Configuration options
        config_group = parser.add_argument_group("Configuration")
        config_group.add_argument(
            "--config-file",
            type=str,
            help="Path to configuration file",
        )
        config_group.add_argument(
            "--project-root",
            type=str,
            help="Root directory of the project (auto-detected if not specified)",
        )

        return parser.parse_args()

    def execute(self, args: Optional[argparse.Namespace] = None) -> int:
        """Execute the efficiency report command."""
        if args is None:
            args = self.parse_arguments()

        try:
            # Load settings
            settings = self._initial_settings or self._load_settings(args.config_file)

            # Initialize efficiency tracker if not provided
            if self.efficiency_tracker is None:
                from ..core.cross_cutting.monitoring.metrics import ApplicationMetrics

                metrics_client = ApplicationMetrics()
                self.efficiency_tracker = EfficiencyTracker(settings, metrics_client)

            # Set up logging based on verbosity
            if args.verbose:
                logging.getLogger("pytest_analyzer").setLevel(logging.DEBUG)

            # Generate report data
            report_data = self.generate_report(args)

            # Display or save report
            if args.output_file:
                self._save_report(report_data, args.output_file, args.format)
                console.print(f"✅ Report saved to: {args.output_file}")
            else:
                self._display_report(report_data, args)

            return 0

        except Exception as e:
            console.print(f"❌ Error generating efficiency report: {e}", style="red")
            logger.exception("Error during efficiency report generation")
            return 1

    def generate_report(self, args: argparse.Namespace) -> Dict[str, Any]:
        """Generate efficiency report data based on arguments."""
        # Calculate time range
        start_date, end_date = self._calculate_time_range(args)

        # Get sessions data
        sessions_data = self._get_sessions_data(start_date, end_date)

        # Calculate metrics
        metrics = self._calculate_metrics(sessions_data)

        # Build report data
        report_data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "time_range": args.time_range,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "total_sessions": len(sessions_data),
            },
            "metrics": metrics,
            "sessions": sessions_data if args.verbose else [],
        }

        # Add comparative analysis if requested
        if args.compare:
            comparison_data = self._generate_comparative_analysis(start_date, end_date)
            report_data["comparison"] = comparison_data

        # Add trends if requested
        if args.trends:
            trends_data = self._generate_trends_analysis(sessions_data)
            report_data["trends"] = trends_data

        # Add recommendations if requested
        if args.recommendations:
            recommendations = self.efficiency_tracker.generate_recommendations()
            report_data["recommendations"] = recommendations

        return report_data

    def _calculate_time_range(
        self, args: argparse.Namespace
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Calculate start and end dates based on time range arguments."""
        now = datetime.now()

        if args.start_date and args.end_date:
            start_date = datetime.fromisoformat(args.start_date)
            end_date = datetime.fromisoformat(args.end_date)
            return start_date, end_date

        if args.time_range == "day":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif args.time_range == "week":
            start_date = now - timedelta(days=7)
            end_date = now
        elif args.time_range == "month":
            start_date = now - timedelta(days=30)
            end_date = now
        else:  # all
            start_date = None
            end_date = None

        return start_date, end_date

    def _get_sessions_data(
        self, start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Retrieve sessions data from the efficiency tracker database."""
        db_path = self.efficiency_tracker.db_path

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Build query based on date range
            query = """
                SELECT id, start_time, end_time, total_tokens, total_fixes,
                       successful_fixes, efficiency_score
                FROM sessions
                WHERE end_time IS NOT NULL
            """
            params = []

            if start_date:
                query += " AND start_time >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND start_time <= ?"
                params.append(end_date.isoformat())

            query += " ORDER BY start_time DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            sessions = []
            for row in rows:
                session = {
                    "id": row[0],
                    "start_time": row[1],
                    "end_time": row[2],
                    "total_tokens": row[3],
                    "total_fixes": row[4],
                    "successful_fixes": row[5],
                    "efficiency_score": row[6],
                }
                sessions.append(session)

            return sessions

    def _calculate_metrics(self, sessions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate aggregate metrics from sessions data."""
        if not sessions_data:
            return {
                "total_sessions": 0,
                "total_tokens": 0,
                "total_fixes": 0,
                "successful_fixes": 0,
                "average_efficiency_score": 0.0,
                "success_rate": 0.0,
                "tokens_per_fix": 0.0,
                "sessions_per_day": 0.0,
            }

        total_tokens = sum(s["total_tokens"] for s in sessions_data)
        total_fixes = sum(s["total_fixes"] for s in sessions_data)
        successful_fixes = sum(s["successful_fixes"] for s in sessions_data)

        efficiency_scores = [
            s["efficiency_score"]
            for s in sessions_data
            if s["efficiency_score"] is not None
        ]
        avg_efficiency = (
            sum(efficiency_scores) / len(efficiency_scores)
            if efficiency_scores
            else 0.0
        )

        success_rate = successful_fixes / total_fixes if total_fixes > 0 else 0.0
        tokens_per_fix = (
            total_tokens / successful_fixes if successful_fixes > 0 else 0.0
        )

        # Calculate sessions per day
        if len(sessions_data) > 1:
            first_session = datetime.fromisoformat(sessions_data[-1]["start_time"])
            last_session = datetime.fromisoformat(sessions_data[0]["start_time"])
            days_span = max(1, (last_session - first_session).days)
            sessions_per_day = len(sessions_data) / days_span
        else:
            sessions_per_day = len(sessions_data)

        return {
            "total_sessions": len(sessions_data),
            "total_tokens": total_tokens,
            "total_fixes": total_fixes,
            "successful_fixes": successful_fixes,
            "average_efficiency_score": avg_efficiency,
            "success_rate": success_rate,
            "tokens_per_fix": tokens_per_fix,
            "sessions_per_day": sessions_per_day,
        }

    def _generate_comparative_analysis(
        self, start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> Dict[str, Any]:
        """Generate comparative analysis with previous period."""
        if not start_date or not end_date:
            return {"error": "Comparison requires specific date range"}

        # Calculate previous period
        period_length = end_date - start_date
        prev_end_date = start_date
        prev_start_date = start_date - period_length

        # Get data for both periods
        current_sessions = self._get_sessions_data(start_date, end_date)
        previous_sessions = self._get_sessions_data(prev_start_date, prev_end_date)

        current_metrics = self._calculate_metrics(current_sessions)
        previous_metrics = self._calculate_metrics(previous_sessions)

        # Calculate changes
        changes = {}
        for key in current_metrics:
            if isinstance(current_metrics[key], (int, float)):
                current_val = current_metrics[key]
                previous_val = previous_metrics[key]

                if previous_val > 0:
                    change_percent = ((current_val - previous_val) / previous_val) * 100
                else:
                    change_percent = 100 if current_val > 0 else 0

                changes[key] = {
                    "current": current_val,
                    "previous": previous_val,
                    "change_percent": change_percent,
                    "trend": "up"
                    if change_percent > 0
                    else "down"
                    if change_percent < 0
                    else "stable",
                }

        return {
            "current_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "metrics": current_metrics,
            },
            "previous_period": {
                "start": prev_start_date.isoformat(),
                "end": prev_end_date.isoformat(),
                "metrics": previous_metrics,
            },
            "changes": changes,
        }

    def _generate_trends_analysis(
        self, sessions_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate trend analysis from sessions data."""
        if len(sessions_data) < 2:
            return {"error": "Insufficient data for trend analysis"}

        # Group sessions by day for daily trends
        daily_metrics = {}
        for session in sessions_data:
            date_str = session["start_time"][:10]  # Extract YYYY-MM-DD

            if date_str not in daily_metrics:
                daily_metrics[date_str] = {
                    "sessions": 0,
                    "tokens": 0,
                    "fixes": 0,
                    "successful_fixes": 0,
                    "efficiency_scores": [],
                }

            daily_metrics[date_str]["sessions"] += 1
            daily_metrics[date_str]["tokens"] += session["total_tokens"]
            daily_metrics[date_str]["fixes"] += session["total_fixes"]
            daily_metrics[date_str]["successful_fixes"] += session["successful_fixes"]

            if session["efficiency_score"] is not None:
                daily_metrics[date_str]["efficiency_scores"].append(
                    session["efficiency_score"]
                )

        # Calculate daily averages
        trend_data = []
        for date_str, metrics in sorted(daily_metrics.items()):
            avg_efficiency = (
                sum(metrics["efficiency_scores"]) / len(metrics["efficiency_scores"])
                if metrics["efficiency_scores"]
                else 0.0
            )

            trend_data.append(
                {
                    "date": date_str,
                    "sessions": metrics["sessions"],
                    "tokens": metrics["tokens"],
                    "fixes": metrics["fixes"],
                    "successful_fixes": metrics["successful_fixes"],
                    "success_rate": metrics["successful_fixes"] / metrics["fixes"]
                    if metrics["fixes"] > 0
                    else 0.0,
                    "average_efficiency": avg_efficiency,
                }
            )

        # Calculate overall trend direction
        if len(trend_data) >= 2:
            first_efficiency = trend_data[0]["average_efficiency"]
            last_efficiency = trend_data[-1]["average_efficiency"]

            if last_efficiency > first_efficiency * 1.1:
                overall_trend = "improving"
            elif last_efficiency < first_efficiency * 0.9:
                overall_trend = "declining"
            else:
                overall_trend = "stable"
        else:
            overall_trend = "insufficient_data"

        return {
            "daily_trends": trend_data,
            "overall_trend": overall_trend,
            "trend_summary": f"Efficiency trend is {overall_trend} over the analyzed period",
        }

    def _load_settings(self, config_file: Optional[str]) -> Settings:
        """Load settings from configuration file."""
        try:
            return load_settings(config_file)
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")
            return Settings()

    def _save_report(
        self, report_data: Dict[str, Any], output_file: str, format_type: str
    ):
        """Save report to file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format_type == "json":
            with open(output_path, "w") as f:
                json.dump(report_data, f, indent=2)
        else:
            with open(output_path, "w") as f:
                f.write(self._format_table_report(report_data))

    def _display_report(self, report_data: Dict[str, Any], args: argparse.Namespace):
        """Display report to console."""
        if args.format == "json":
            print(json.dumps(report_data, indent=2))
        else:
            self._display_table_report(report_data, args)

    def _display_table_report(
        self, report_data: Dict[str, Any], args: argparse.Namespace
    ):
        """Display table-formatted report to console."""
        metadata = report_data["metadata"]
        metrics = report_data["metrics"]

        # Header
        console.print(
            Panel(
                f"Efficiency Report - {metadata['time_range'].title()} View",
                title="📊 Development Efficiency Analysis",
                border_style="blue",
            )
        )

        # Main metrics table
        metrics_table = Table(title="Key Metrics")
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", style="white")

        metrics_table.add_row("Total Sessions", str(metrics["total_sessions"]))
        metrics_table.add_row("Total Tokens Used", f"{metrics['total_tokens']:,}")
        metrics_table.add_row("Total Fixes Attempted", str(metrics["total_fixes"]))
        metrics_table.add_row("Successful Fixes", str(metrics["successful_fixes"]))
        metrics_table.add_row("Success Rate", f"{metrics['success_rate']:.1%}")
        metrics_table.add_row(
            "Avg Efficiency Score", f"{metrics['average_efficiency_score']:.3f}"
        )
        metrics_table.add_row("Tokens per Fix", f"{metrics['tokens_per_fix']:.1f}")
        metrics_table.add_row("Sessions per Day", f"{metrics['sessions_per_day']:.1f}")

        console.print(metrics_table)

        # Comparison table if available
        if "comparison" in report_data and "changes" in report_data["comparison"]:
            changes = report_data["comparison"]["changes"]
            comparison_table = Table(title="Period Comparison")
            comparison_table.add_column("Metric", style="cyan")
            comparison_table.add_column("Current", style="white")
            comparison_table.add_column("Previous", style="white")
            comparison_table.add_column("Change", style="white")

            for metric_name, change_data in changes.items():
                if metric_name in [
                    "average_efficiency_score",
                    "success_rate",
                    "tokens_per_fix",
                ]:
                    current_val = f"{change_data['current']:.3f}"
                    previous_val = f"{change_data['previous']:.3f}"
                else:
                    current_val = str(change_data["current"])
                    previous_val = str(change_data["previous"])

                change_percent = change_data["change_percent"]
                trend_icon = (
                    "📈"
                    if change_data["trend"] == "up"
                    else "📉"
                    if change_data["trend"] == "down"
                    else "➡️"
                )
                change_str = f"{trend_icon} {change_percent:+.1f}%"

                comparison_table.add_row(
                    metric_name.replace("_", " ").title(),
                    current_val,
                    previous_val,
                    change_str,
                )

            console.print(comparison_table)

        # Recommendations if available
        if "recommendations" in report_data:
            console.print("\n[yellow]💡 Recommendations:[/yellow]")
            for recommendation in report_data["recommendations"]:
                console.print(f"  • {recommendation}")

        # Trends summary if available
        if "trends" in report_data and "trend_summary" in report_data["trends"]:
            console.print(
                f"\n[blue]📈 Trend Analysis:[/blue] {report_data['trends']['trend_summary']}"
            )

    def _format_table_report(self, report_data: Dict[str, Any]) -> str:
        """Format report as plain text table."""
        lines = ["Development Efficiency Report", "=" * 50, ""]

        metadata = report_data["metadata"]
        metrics = report_data["metrics"]

        # Metadata
        lines.append(f"Generated: {metadata['generated_at']}")
        lines.append(f"Time Range: {metadata['time_range']}")
        lines.append(f"Total Sessions: {metadata['total_sessions']}")
        lines.append("")

        # Key metrics
        lines.append("Key Metrics:")
        lines.append(f"  Total Tokens Used: {metrics['total_tokens']:,}")
        lines.append(f"  Total Fixes Attempted: {metrics['total_fixes']}")
        lines.append(f"  Successful Fixes: {metrics['successful_fixes']}")
        lines.append(f"  Success Rate: {metrics['success_rate']:.1%}")
        lines.append(
            f"  Average Efficiency Score: {metrics['average_efficiency_score']:.3f}"
        )
        lines.append(f"  Tokens per Fix: {metrics['tokens_per_fix']:.1f}")
        lines.append(f"  Sessions per Day: {metrics['sessions_per_day']:.1f}")
        lines.append("")

        # Recommendations if available
        if "recommendations" in report_data:
            lines.append("Recommendations:")
            for recommendation in report_data["recommendations"]:
                lines.append(f"  • {recommendation}")
            lines.append("")

        return "\n".join(lines)


def main():
    """Main entry point for the efficiency-report command."""
    command = EfficiencyReportCommand()
    return command.execute()


if __name__ == "__main__":
    import sys

    sys.exit(main())
