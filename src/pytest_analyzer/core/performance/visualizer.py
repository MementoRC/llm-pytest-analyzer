"""
Visualization tools for performance benchmark data.

This module provides tools for creating charts, graphs, and visual reports
from benchmark results and trend data.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .metrics import MetricType
from .storage import BenchmarkStorage


class BenchmarkVisualizer:
    """
    Visualization generator for benchmark data.

    Creates various charts and visual reports for performance analysis.
    Note: This is a text-based visualizer that generates data for external
    visualization tools like matplotlib, plotly, or web frontends.
    """

    def __init__(self, storage: BenchmarkStorage):
        """Initialize visualizer with storage backend."""
        self.storage = storage

    def generate_trend_chart_data(
        self, suite_name: str, test_name: str, metric_name: str, days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate data for a trend chart showing metric values over time.

        Args:
            suite_name: Name of the benchmark suite
            test_name: Name of the test
            metric_name: Name of the metric to visualize
            days: Number of days of history to include

        Returns:
            Chart data structure suitable for visualization libraries
        """
        # Get historical data
        history = self.storage.get_metric_history(
            suite_name, test_name, metric_name, days
        )

        if not history:
            return {
                "error": "No data available",
                "suite_name": suite_name,
                "test_name": test_name,
                "metric_name": metric_name,
            }

        # Extract data points
        timestamps = [point["run_time"] for point in history]
        values = [point["value"] for point in history]

        # Ensure values are numeric for statistics calculations
        numeric_values = [v for v in values if isinstance(v, (int, float))]

        # Calculate trend statistics
        if len(numeric_values) > 1:
            import statistics

            recent_numeric = numeric_values[
                -min(5, len(numeric_values)) :
            ]  # Last 5 values
            baseline_numeric = numeric_values[
                : min(5, len(numeric_values))
            ]  # First 5 values

            trend_stats = {
                "mean": statistics.mean(numeric_values),
                "median": statistics.median(numeric_values),
                "stdev": statistics.stdev(numeric_values)
                if len(numeric_values) > 1
                else 0,
                "min": min(numeric_values),
                "max": max(numeric_values),
                "recent_mean": statistics.mean(recent_numeric),
                "baseline_mean": statistics.mean(baseline_numeric),
                "trend_direction": "improving"
                if statistics.mean(recent_numeric) < statistics.mean(baseline_numeric)
                else "declining",
            }
        else:
            # Use first numeric value or fallback to 0
            first_numeric = numeric_values[0] if numeric_values else 0
            trend_stats = {
                "mean": first_numeric,
                "median": first_numeric,
                "stdev": 0,
                "min": first_numeric,
                "max": first_numeric,
                "recent_mean": first_numeric,
                "baseline_mean": first_numeric,
                "trend_direction": "stable",
            }

        return {
            "chart_type": "line",
            "title": f"{metric_name} Trend - {test_name}",
            "subtitle": f"Last {days} days",
            "x_axis": {
                "label": "Date",
                "type": "datetime",
                "data": [
                    ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                    for ts in timestamps
                ],
            },
            "y_axis": {"label": f"{metric_name}", "type": "numeric", "data": values},
            "series": [
                {
                    "name": metric_name,
                    "type": "line",
                    "data": list(
                        zip(
                            [
                                ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                                for ts in timestamps
                            ],
                            values,
                        )
                    ),
                }
            ],
            "statistics": trend_stats,
            "metadata": {
                "suite_name": suite_name,
                "test_name": test_name,
                "metric_name": metric_name,
                "data_points": len(values),
                "date_range": {
                    "start": timestamps[0].isoformat() if timestamps else None,
                    "end": timestamps[-1].isoformat() if timestamps else None,
                },
            },
        }

    def generate_comparison_chart_data(
        self,
        suite_name: str,
        metric_name: str,
        test_names: Optional[List[str]] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Generate data for comparing a metric across multiple tests.

        Args:
            suite_name: Name of the benchmark suite
            metric_name: Name of the metric to compare
            test_names: List of test names to compare (all if None)
            days: Number of days to look back for latest values

        Returns:
            Chart data structure for comparison visualization
        """
        # Get suite info
        suite = self.storage.load_suite(suite_name)
        if not suite:
            return {"error": f"Suite '{suite_name}' not found"}

        if test_names is None:
            test_names = suite.tests

        # Collect latest values for each test
        comparison_data = []

        for test_name in test_names:
            history = self.storage.get_metric_history(
                suite_name, test_name, metric_name, days
            )

            if history:
                # Get the most recent value
                latest_value = history[-1]["value"]
                latest_timestamp = history[-1]["run_time"]

                # Calculate trend if we have enough data
                trend = "stable"
                if len(history) > 1:
                    older_value = history[0]["value"]
                    if latest_value < older_value * 0.95:
                        trend = "improving"
                    elif latest_value > older_value * 1.05:
                        trend = "declining"

                comparison_data.append(
                    {
                        "test_name": test_name,
                        "value": latest_value,
                        "timestamp": latest_timestamp.isoformat(),
                        "trend": trend,
                        "data_points": len(history),
                    }
                )

        # Sort by value for better visualization
        comparison_data.sort(key=lambda x: x["value"])

        return {
            "chart_type": "bar",
            "title": f"{metric_name} Comparison",
            "subtitle": f"Latest values (last {days} days)",
            "x_axis": {
                "label": "Tests",
                "type": "category",
                "data": [item["test_name"] for item in comparison_data],
            },
            "y_axis": {
                "label": metric_name,
                "type": "numeric",
                "data": [item["value"] for item in comparison_data],
            },
            "series": [
                {
                    "name": metric_name,
                    "type": "bar",
                    "data": [
                        (item["test_name"], item["value"]) for item in comparison_data
                    ],
                }
            ],
            "details": comparison_data,
            "metadata": {
                "suite_name": suite_name,
                "metric_name": metric_name,
                "test_count": len(comparison_data),
                "period_days": days,
            },
        }

    def generate_regression_alert_data(
        self, suite_name: str, days: int = 7
    ) -> Dict[str, Any]:
        """
        Generate data for regression alerts visualization.

        Args:
            suite_name: Name of the benchmark suite
            days: Number of days to analyze for regressions

        Returns:
            Alert data structure with regression information
        """
        # Get recent results
        recent_results = self.storage.get_recent_results(suite_name, days=days)

        # Group by test
        results_by_test = {}
        for result in recent_results:
            if result.test_name not in results_by_test:
                results_by_test[result.test_name] = []
            results_by_test[result.test_name].append(result)

        # Check for regressions
        alerts = []

        for test_name, test_results in results_by_test.items():
            if not test_results:
                continue

            # Get baseline
            baseline = self.storage.get_baseline_result(suite_name, test_name)
            if not baseline:
                continue

            # Check latest result against baseline
            latest_result = test_results[0]  # Results are sorted by time DESC

            if latest_result.status.name != "COMPLETED":
                continue

            # Compare metrics
            for metric in latest_result.metrics:
                baseline_metric = baseline.get_metric(metric.name)
                if not baseline_metric:
                    continue

                # Calculate change percentage
                if baseline_metric.value != 0:
                    change_percent = (
                        (metric.value - baseline_metric.value)
                        / baseline_metric.value
                        * 100
                    )
                else:
                    change_percent = 0

                # Determine if this is a regression (simplified logic)
                is_regression = False
                severity = "info"

                if metric.metric_type in [
                    MetricType.EXECUTION_TIME,
                    MetricType.API_LATENCY,
                ]:
                    # Higher is worse
                    if change_percent > 20:
                        is_regression = True
                        severity = "critical"
                    elif change_percent > 10:
                        is_regression = True
                        severity = "warning"
                elif metric.metric_type in [
                    MetricType.CACHE_HIT_RATE,
                    MetricType.THROUGHPUT,
                ]:
                    # Lower is worse
                    if change_percent < -20:
                        is_regression = True
                        severity = "critical"
                    elif change_percent < -10:
                        is_regression = True
                        severity = "warning"

                if is_regression:
                    alerts.append(
                        {
                            "test_name": test_name,
                            "metric_name": metric.name,
                            "current_value": metric.value,
                            "baseline_value": baseline_metric.value,
                            "change_percent": change_percent,
                            "severity": severity,
                            "timestamp": latest_result.start_time.isoformat(),
                            "metric_type": metric.metric_type.name,
                            "unit": metric.unit,
                        }
                    )

        # Sort alerts by severity and change magnitude
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(
            key=lambda x: (severity_order[x["severity"]], -abs(x["change_percent"]))
        )

        return {
            "suite_name": suite_name,
            "period_days": days,
            "total_alerts": len(alerts),
            "critical_count": len([a for a in alerts if a["severity"] == "critical"]),
            "warning_count": len([a for a in alerts if a["severity"] == "warning"]),
            "alerts": alerts,
            "generated_at": datetime.now().isoformat(),
        }

    def generate_performance_dashboard_data(
        self, suite_name: str, days: int = 7
    ) -> Dict[str, Any]:
        """
        Generate comprehensive dashboard data for a benchmark suite.

        Args:
            suite_name: Name of the benchmark suite
            days: Number of days of data to include

        Returns:
            Complete dashboard data structure
        """
        # Get suite information
        suite = self.storage.load_suite(suite_name)
        if not suite:
            return {"error": f"Suite '{suite_name}' not found"}

        # Get summary statistics
        summary_stats = self.storage.get_summary_stats(suite_name)

        # Get recent results
        recent_results = self.storage.get_recent_results(suite_name, days=days)

        # Calculate test health scores
        test_health = {}
        for test_name in suite.tests:
            test_results = [r for r in recent_results if r.test_name == test_name]

            if test_results:
                completed_count = len(
                    [r for r in test_results if r.status.name == "COMPLETED"]
                )
                health_score = (completed_count / len(test_results)) * 100

                # Get latest execution time if available
                latest_result = test_results[0]
                exec_time_metric = latest_result.get_metric("execution_time_mean")
                latest_exec_time = exec_time_metric.value if exec_time_metric else None

                test_health[test_name] = {
                    "health_score": health_score,
                    "total_runs": len(test_results),
                    "successful_runs": completed_count,
                    "latest_execution_time": latest_exec_time,
                    "last_run": latest_result.start_time.isoformat(),
                }
            else:
                test_health[test_name] = {
                    "health_score": 0,
                    "total_runs": 0,
                    "successful_runs": 0,
                    "latest_execution_time": None,
                    "last_run": None,
                }

        # Generate trend data for key metrics
        key_metrics = ["execution_time_mean", "memory_usage", "cpu_usage"]
        trend_summaries = {}

        for metric_name in key_metrics:
            metric_trends = {}
            for test_name in suite.tests[:5]:  # Limit to first 5 tests for performance
                history = self.storage.get_metric_history(
                    suite_name, test_name, metric_name, days
                )
                if history and len(history) > 1:
                    values = [h["value"] for h in history]
                    trend_direction = "stable"
                    if values[-1] < values[0] * 0.95:
                        trend_direction = "improving"
                    elif values[-1] > values[0] * 1.05:
                        trend_direction = "declining"

                    metric_trends[test_name] = {
                        "direction": trend_direction,
                        "latest_value": values[-1],
                        "data_points": len(values),
                    }

            trend_summaries[metric_name] = metric_trends

        # Get regression alerts
        regression_data = self.generate_regression_alert_data(suite_name, days)

        return {
            "suite_info": {
                "name": suite.name,
                "description": suite.description,
                "total_tests": len(suite.tests),
                "tags": suite.tags,
            },
            "summary_statistics": summary_stats,
            "test_health": test_health,
            "trend_summaries": trend_summaries,
            "regression_alerts": {
                "total_count": regression_data["total_alerts"],
                "critical_count": regression_data["critical_count"],
                "warning_count": regression_data["warning_count"],
                "recent_alerts": regression_data["alerts"][:10],  # Top 10 alerts
            },
            "period_info": {
                "days": days,
                "start_date": (datetime.now() - timedelta(days=days)).isoformat(),
                "end_date": datetime.now().isoformat(),
            },
            "generated_at": datetime.now().isoformat(),
        }

    def export_chart_data(
        self,
        chart_data: Dict[str, Any],
        output_path: Union[str, Path],
        format_type: str = "json",
    ):
        """
        Export chart data to file.

        Args:
            chart_data: Chart data structure to export
            output_path: Path to save the exported data
            format_type: Export format ("json", "csv")
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format_type.lower() == "json":
            with open(output_path, "w") as f:
                json.dump(chart_data, f, indent=2)

        elif format_type.lower() == "csv":
            # Export as CSV (simplified - works best for trend data)
            import csv

            with open(output_path, "w", newline="") as f:
                writer = csv.writer(f)

                if chart_data.get("chart_type") == "line" and "series" in chart_data:
                    # Write header
                    writer.writerow(["timestamp", "value"])

                    # Write data points
                    for timestamp, value in chart_data["series"][0]["data"]:
                        writer.writerow([timestamp, value])

                elif chart_data.get("chart_type") == "bar" and "series" in chart_data:
                    # Write header
                    writer.writerow(["category", "value"])

                    # Write data points
                    for category, value in chart_data["series"][0]["data"]:
                        writer.writerow([category, value])

        else:
            raise ValueError(f"Unsupported export format: {format_type}")

    def generate_html_report(
        self,
        suite_name: str,
        output_path: Union[str, Path],
        days: int = 7,
        include_charts: bool = True,
    ):
        """
        Generate an HTML performance report.

        Args:
            suite_name: Name of the benchmark suite
            output_path: Path to save the HTML report
            days: Number of days of data to include
            include_charts: Whether to include chart data for client-side rendering
        """
        dashboard_data = self.generate_performance_dashboard_data(suite_name, days)

        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Performance Report - {suite_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; }}
                .metric {{ margin: 10px 0; padding: 10px; border-left: 3px solid #007bff; }}
                .alert {{ margin: 10px 0; padding: 10px; border-left: 3px solid #dc3545; }}
                .warning {{ border-left-color: #ffc107; }}
                .success {{ border-left-color: #28a745; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Performance Report: {suite_name}</h1>
                <p>Generated: {generated_at}</p>
                <p>Period: {days} days</p>
            </div>

            <h2>Summary Statistics</h2>
            <div class="metric">
                <strong>Total Results:</strong> {total_results}<br>
                <strong>Recent Results:</strong> {recent_results}<br>
                <strong>Test Health:</strong> {test_health_summary}
            </div>

            <h2>Regression Alerts</h2>
            {alerts_html}

            <h2>Test Health Status</h2>
            <table>
                <tr>
                    <th>Test Name</th>
                    <th>Health Score</th>
                    <th>Total Runs</th>
                    <th>Successful Runs</th>
                    <th>Latest Execution Time</th>
                </tr>
                {test_health_rows}
            </table>

            {chart_data_script}
        </body>
        </html>
        """

        # Build alerts HTML
        alerts_html = ""
        if dashboard_data["regression_alerts"]["total_count"] > 0:
            for alert in dashboard_data["regression_alerts"]["recent_alerts"]:
                severity_class = (
                    "alert" if alert["severity"] == "critical" else "warning"
                )
                alerts_html += f"""
                <div class="{severity_class}">
                    <strong>{alert["test_name"]}</strong> - {alert["metric_name"]}<br>
                    Change: {alert["change_percent"]:.1f}%
                    ({alert["current_value"]:.3f} vs {alert["baseline_value"]:.3f} {alert["unit"]})
                </div>
                """
        else:
            alerts_html = (
                '<div class="success">No performance regressions detected.</div>'
            )

        # Build test health rows
        test_health_rows = ""
        for test_name, health_data in dashboard_data["test_health"].items():
            exec_time = (
                f"{health_data['latest_execution_time']:.3f}s"
                if health_data["latest_execution_time"]
                else "N/A"
            )
            test_health_rows += f"""
            <tr>
                <td>{test_name}</td>
                <td>{health_data["health_score"]:.1f}%</td>
                <td>{health_data["total_runs"]}</td>
                <td>{health_data["successful_runs"]}</td>
                <td>{exec_time}</td>
            </tr>
            """

        # Include chart data as JavaScript if requested
        chart_data_script = ""
        if include_charts:
            chart_data_script = f"""
            <script>
                window.performanceData = {json.dumps(dashboard_data, indent=2)};
                console.log('Performance data loaded:', window.performanceData);
            </script>
            """

        # Calculate test health summary
        health_scores = [
            data["health_score"] for data in dashboard_data["test_health"].values()
        ]
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 0

        # Format the HTML
        html_content = html_template.format(
            suite_name=dashboard_data["suite_info"]["name"],
            generated_at=dashboard_data["generated_at"],
            days=days,
            total_results=dashboard_data["summary_statistics"].get("total_results", 0),
            recent_results=dashboard_data["summary_statistics"].get(
                "recent_results", 0
            ),
            test_health_summary=f"{avg_health:.1f}% average",
            alerts_html=alerts_html,
            test_health_rows=test_health_rows,
            chart_data_script=chart_data_script,
        )

        # Write to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(html_content)
