"""
Report generation models for the Pytest Analyzer GUI.

This module contains the ReportGenerator class and related functionality for
generating comprehensive reports of test analysis results.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from .session import SessionData
from .test_results_model import TestResult, TestStatus

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Available report formats."""

    HTML = "html"
    PDF = "pdf"
    JSON = "json"
    CSV = "csv"


class ReportType(Enum):
    """Types of reports that can be generated."""

    SUMMARY = "summary"
    FULL_ANALYSIS = "full_analysis"
    COVERAGE = "coverage"
    FIX_HISTORY = "fix_history"
    SESSION = "session"


@dataclass
class ReportConfig:
    """Configuration for report generation."""

    title: Optional[str] = None
    format: ReportFormat = ReportFormat.HTML
    report_type: ReportType = ReportType.SUMMARY
    include_passed_tests: bool = False
    include_skipped_tests: bool = False
    include_analysis_details: bool = True
    include_fix_suggestions: bool = True
    include_bookmarks: bool = True
    include_history: bool = True
    include_charts: bool = True
    include_metadata: bool = True
    custom_css: Optional[str] = None
    template_path: Optional[Path] = None
    output_path: Optional[Path] = None

    # Advanced options
    group_by_file: bool = True
    sort_by_severity: bool = True
    max_suggestion_length: int = 1000
    include_code_snippets: bool = True
    anonymize_paths: bool = False


@dataclass
class ReportStatistics:
    """Statistics included in reports."""

    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    error_tests: int = 0
    skipped_tests: int = 0

    total_suggestions: int = 0
    high_confidence_suggestions: int = 0
    applied_fixes: int = 0

    analysis_duration: float = 0.0
    generation_time: datetime = field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """Calculate test success rate."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100

    @property
    def failure_rate(self) -> float:
        """Calculate test failure rate."""
        if self.total_tests == 0:
            return 0.0
        return ((self.failed_tests + self.error_tests) / self.total_tests) * 100


class ReportGenerator(QObject):
    """Generates comprehensive reports from test analysis data."""

    report_generated = Signal(str, bool)  # file_path, success
    progress_updated = Signal(int)  # percentage

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.templates_dir = Path(__file__).parent.parent / "templates" / "reports"
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Initialize templates dictionary
        self._templates = {}

        # Initialize default templates
        self._create_default_templates()

    def generate_report(
        self,
        config: ReportConfig,
        test_results: Optional[List[TestResult]] = None,
        analysis_results: Optional[List[Any]] = None,
        session_data: Optional[SessionData] = None,
    ) -> str:
        """Generate a report based on the configuration."""
        try:
            # Calculate statistics
            stats = self._calculate_statistics(test_results, analysis_results, session_data)

            # Generate report based on format
            if config.format == ReportFormat.HTML:
                content = self._generate_html_report(
                    test_results, analysis_results, config, stats, session_data
                )
            elif config.format == ReportFormat.PDF:
                content = self._generate_pdf_report(
                    test_results, analysis_results, config, stats, session_data
                )
            elif config.format == ReportFormat.JSON:
                content = self._generate_json_report(
                    test_results, analysis_results, config, stats, session_data
                )
            elif config.format == ReportFormat.CSV:
                content = self._generate_csv_report(
                    test_results, analysis_results, config, stats, session_data
                )
            else:
                raise ValueError(f"Unsupported report format: {config.format}")

            # Save to file if output path is specified
            if config.output_path:
                config.output_path.write_text(content, encoding="utf-8")
                output_file = str(config.output_path)
            else:
                # Generate default filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"pytest_report_{timestamp}.{config.format.value}"
                output_file = str(Path.cwd() / filename)
                Path(output_file).write_text(content, encoding="utf-8")

            self.report_generated.emit(output_file, True)
            logger.info(f"Report generated successfully: {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            self.report_generated.emit("", False)
            raise

    def _calculate_statistics(
        self,
        test_results: Optional[List[TestResult]],
        analysis_results: Optional[List[Any]] = None,
        session_data: Optional[SessionData] = None,
    ) -> ReportStatistics:
        """Calculate report statistics."""
        stats = ReportStatistics()

        if test_results:
            stats.total_tests = len(test_results)

            for result in test_results:
                if result.status == TestStatus.PASSED:
                    stats.passed_tests += 1
                elif result.status == TestStatus.FAILED:
                    stats.failed_tests += 1
                elif result.status == TestStatus.ERROR:
                    stats.error_tests += 1
                elif result.status == TestStatus.SKIPPED:
                    stats.skipped_tests += 1

                if hasattr(result, "suggestions") and result.suggestions:
                    stats.total_suggestions += len(result.suggestions)
                    stats.high_confidence_suggestions += sum(
                        1
                        for s in result.suggestions
                        if hasattr(s, "confidence") and s.confidence > 0.8
                    )

        # Add session data statistics if available
        if session_data:
            # Could add more session-specific statistics here
            pass

        return stats

    def _generate_html_report(
        self,
        test_results: Optional[List[TestResult]],
        analysis_results: Optional[List[Any]],
        config: ReportConfig,
        stats: ReportStatistics,
        session_data: Optional[SessionData] = None,
    ) -> str:
        """Generate HTML report."""
        # Load template
        template_path = config.template_path or (self.templates_dir / "default.html")

        if template_path.exists():
            template = template_path.read_text(encoding="utf-8")
        else:
            template = self._get_default_html_template()

        # Prepare template variables
        variables = {
            "title": config.title or "Pytest Analysis Report",
            "generation_time": stats.generation_time.strftime("%Y-%m-%d %H:%M:%S"),
            "statistics": stats,
            "test_results": test_results or [],
            "session_data": session_data,
            "config": config,
            "charts_data": self._generate_charts_data(test_results, stats)
            if config.include_charts and test_results
            else None,
        }

        # Replace template variables
        content = self._render_template(template, variables)

        return content

    def _generate_pdf_report(
        self,
        test_results: Optional[List[TestResult]],
        analysis_results: Optional[List[Any]],
        config: ReportConfig,
        stats: ReportStatistics,
        session_data: Optional[SessionData] = None,
    ) -> str:
        """Generate PDF report (requires additional dependencies)."""
        # For now, generate HTML and suggest conversion
        # In a real implementation, you might use libraries like WeasyPrint or reportlab
        html_content = self._generate_html_report(
            test_results, analysis_results, config, stats, session_data
        )

        # Save HTML temporarily and suggest PDF conversion
        html_file = (
            config.output_path.with_suffix(".html")
            if config.output_path
            else Path("temp_report.html")
        )
        html_file.write_text(html_content, encoding="utf-8")

        logger.warning(
            "PDF generation requires additional dependencies. HTML report generated instead."
        )
        logger.info("Consider using tools like wkhtmltopdf or WeasyPrint to convert HTML to PDF")

        return html_content

    def _generate_json_report(
        self,
        test_results: Optional[List[TestResult]],
        analysis_results: Optional[List[Any]],
        config: ReportConfig,
        stats: ReportStatistics,
        session_data: Optional[SessionData] = None,
    ) -> str:
        """Generate JSON report."""
        from dataclasses import asdict

        # Convert test results to dictionaries
        results_data = []
        if test_results:
            for result in test_results:
                result_dict = {
                    "name": result.name,
                    "status": result.status.name if hasattr(result, "status") else "UNKNOWN",
                    "duration": getattr(result, "duration", None),
                    "file_path": str(result.file_path)
                    if hasattr(result, "file_path") and result.file_path
                    else None,
                    "failure_details": asdict(result.failure_details)
                    if hasattr(result, "failure_details") and result.failure_details
                    else None,
                    "suggestions": [asdict(s) for s in result.suggestions]
                    if hasattr(result, "suggestions") and result.suggestions
                    else [],
                    "analysis_status": result.analysis_status.name
                    if hasattr(result, "analysis_status")
                    else "NOT_ANALYZED",
                }
                results_data.append(result_dict)

        # Convert stats to JSON-serializable format
        stats_dict = asdict(stats)
        if "generation_time" in stats_dict:
            stats_dict["generation_time"] = stats.generation_time.isoformat()

        # Convert config to JSON-serializable format
        config_dict = asdict(config)
        if "output_path" in config_dict and config_dict["output_path"]:
            config_dict["output_path"] = str(config_dict["output_path"])
        if "template_path" in config_dict and config_dict["template_path"]:
            config_dict["template_path"] = str(config_dict["template_path"])
        # Convert enum values to strings
        if "format" in config_dict:
            config_dict["format"] = config.format.value
        if "report_type" in config_dict:
            config_dict["report_type"] = config.report_type.value

        # Prepare report data
        report_data = {
            "metadata": {
                "title": config.title,
                "format": config.format.value,
                "type": config.report_type.value,
                "generation_time": stats.generation_time.isoformat(),
                "generator": "Pytest Analyzer GUI",
                "version": "1.0",
            },
            "statistics": stats_dict,
            "configuration": config_dict,
            "test_results": results_data,
            "session_data": session_data.to_dict() if session_data else None,
        }

        return json.dumps(report_data, indent=2, ensure_ascii=False)

    def _generate_csv_report(
        self,
        test_results: Optional[List[TestResult]],
        analysis_results: Optional[List[Any]],
        config: ReportConfig,
        stats: ReportStatistics,
        session_data: Optional[SessionData] = None,
    ) -> str:
        """Generate CSV report."""
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        # Write header
        headers = [
            "Test Name",
            "Status",
            "Duration",
            "File Path",
            "Failure Message",
            "Suggestions Count",
            "Analysis Status",
        ]
        writer.writerow(headers)

        # Write test results
        if test_results:
            for result in test_results:
                row = [
                    result.name,
                    result.status.name if hasattr(result, "status") else "UNKNOWN",
                    getattr(result, "duration", ""),
                    str(result.file_path)
                    if hasattr(result, "file_path") and result.file_path
                    else "",
                    result.failure_details.message
                    if hasattr(result, "failure_details") and result.failure_details
                    else "",
                    len(result.suggestions)
                    if hasattr(result, "suggestions") and result.suggestions
                    else 0,
                    result.analysis_status.name
                    if hasattr(result, "analysis_status")
                    else "NOT_ANALYZED",
                ]
                writer.writerow(row)

        return output.getvalue()

    def _generate_charts_data(
        self, test_results: Optional[List[TestResult]], stats: ReportStatistics
    ) -> Dict[str, Any]:
        """Generate data for charts and graphs."""
        # Status distribution
        status_data = {
            "passed": stats.passed_tests,
            "failed": stats.failed_tests,
            "error": stats.error_tests,
            "skipped": stats.skipped_tests,
        }

        # File-based distribution
        file_distribution = {}
        for result in test_results:
            if result.file_path:
                file_key = result.file_path.name
                if file_key not in file_distribution:
                    file_distribution[file_key] = {"passed": 0, "failed": 0, "error": 0}

                if result.status == TestStatus.PASSED:
                    file_distribution[file_key]["passed"] += 1
                elif result.status == TestStatus.FAILED:
                    file_distribution[file_key]["failed"] += 1
                elif result.status == TestStatus.ERROR:
                    file_distribution[file_key]["error"] += 1

        # Duration analysis
        durations = [result.duration for result in test_results if result.duration > 0]
        duration_stats = {
            "min": min(durations) if durations else 0,
            "max": max(durations) if durations else 0,
            "avg": sum(durations) / len(durations) if durations else 0,
        }

        return {
            "status_distribution": status_data,
            "file_distribution": file_distribution,
            "duration_statistics": duration_stats,
        }

    def _render_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Simple template rendering (replace with Jinja2 for advanced templating)."""
        content = template

        # Simple variable replacement
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"

            if key == "statistics":
                stats_html = self._render_statistics_html(value)
                content = content.replace(placeholder, stats_html)
            elif key == "test_results":
                results_html = self._render_test_results_html(value, variables.get("config"))
                content = content.replace(placeholder, results_html)
            elif key == "charts_data" and value:
                charts_html = self._render_charts_html(value)
                content = content.replace(placeholder, charts_html)
            else:
                content = content.replace(placeholder, str(value) if value is not None else "")

        return content

    def _render_statistics_html(self, stats: ReportStatistics) -> str:
        """Render statistics as HTML."""
        return f"""
        <div class="statistics">
            <h2>Test Statistics</h2>
            <div class="stat-grid">
                <div class="stat-item">
                    <span class="stat-value">{stats.total_tests}</span>
                    <span class="stat-label">Total Tests</span>
                </div>
                <div class="stat-item success">
                    <span class="stat-value">{stats.passed_tests}</span>
                    <span class="stat-label">Passed</span>
                </div>
                <div class="stat-item failure">
                    <span class="stat-value">{stats.failed_tests}</span>
                    <span class="stat-label">Failed</span>
                </div>
                <div class="stat-item error">
                    <span class="stat-value">{stats.error_tests}</span>
                    <span class="stat-label">Errors</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value">{stats.success_rate:.1f}%</span>
                    <span class="stat-label">Success Rate</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value">{stats.total_suggestions}</span>
                    <span class="stat-label">AI Suggestions</span>
                </div>
            </div>
        </div>
        """

    def _render_test_results_html(
        self, test_results: List[TestResult], config: Optional[ReportConfig] = None
    ) -> str:
        """Render test results as HTML."""
        if not test_results:
            return "<p>No test results to display.</p>"

        html_parts = ["<div class='test-results'>", "<h2>Test Results</h2>"]

        # Group by file if configured
        if config and config.group_by_file:
            from collections import defaultdict

            grouped_results = defaultdict(list)

            for result in test_results:
                file_key = str(result.file_path) if result.file_path else "Unknown"
                grouped_results[file_key].append(result)

            for file_path, results in grouped_results.items():
                html_parts.append(f"<h3>File: {Path(file_path).name}</h3>")
                html_parts.append("<div class='file-results'>")

                for result in results:
                    html_parts.append(self._render_single_test_html(result, config))

                html_parts.append("</div>")
        else:
            for result in test_results:
                html_parts.append(self._render_single_test_html(result, config))

        html_parts.append("</div>")
        return "\n".join(html_parts)

    def _render_single_test_html(
        self, result: TestResult, config: Optional[ReportConfig] = None
    ) -> str:
        """Render a single test result as HTML."""
        status_class = result.status.name.lower()

        html = f"""
        <div class="test-result {status_class}">
            <div class="test-header">
                <h4 class="test-name">{result.name}</h4>
                <span class="test-status {status_class}">{result.status.name}</span>
                <span class="test-duration">{result.duration:.3f}s</span>
            </div>
        """

        # Add failure details if present
        if result.failure_details and result.status in [TestStatus.FAILED, TestStatus.ERROR]:
            html += f"""
            <div class="failure-details">
                <h5>Failure Details:</h5>
                <pre class="failure-message">{result.failure_details.message}</pre>
                {f'<pre class="traceback">{result.failure_details.traceback}</pre>' if result.failure_details.traceback else ""}
            </div>
            """

        # Add suggestions if configured and available
        if config and config.include_fix_suggestions and result.suggestions:
            html += "<div class='suggestions'><h5>AI Suggestions:</h5>"

            for i, suggestion in enumerate(result.suggestions[:3]):  # Limit to top 3
                confidence_class = (
                    "high"
                    if suggestion.confidence > 0.8
                    else "medium"
                    if suggestion.confidence > 0.5
                    else "low"
                )

                suggestion_text = suggestion.suggestion
                if (
                    config.max_suggestion_length
                    and len(suggestion_text) > config.max_suggestion_length
                ):
                    suggestion_text = suggestion_text[: config.max_suggestion_length] + "..."

                html += f"""
                <div class="suggestion {confidence_class}">
                    <div class="suggestion-header">
                        <span class="confidence">Confidence: {suggestion.confidence:.1%}</span>
                    </div>
                    <p class="suggestion-text">{suggestion_text}</p>
                </div>
                """

            html += "</div>"

        html += "</div>"
        return html

    def _render_charts_html(self, charts_data: Dict[str, Any]) -> str:
        """Render charts as HTML with Chart.js."""
        return f"""
        <div class="charts">
            <h2>Visual Analysis</h2>
            <div class="chart-container">
                <canvas id="statusChart"></canvas>
            </div>
            <script>
                const statusData = {json.dumps(charts_data["status_distribution"])};
                // Chart.js implementation would go here
            </script>
        </div>
        """

    def _get_default_html_template(self) -> str:
        """Get the default HTML template."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 30px;
        }
        .header-info {
            background: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-item {
            text-align: center;
            padding: 20px;
            border-radius: 8px;
            background: #f8f9fa;
            border: 1px solid #e9ecef;
        }
        .stat-value {
            display: block;
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }
        .stat-label {
            display: block;
            color: #7f8c8d;
            margin-top: 5px;
        }
        .success { border-left: 4px solid #27ae60; }
        .failure { border-left: 4px solid #e74c3c; }
        .error { border-left: 4px solid #f39c12; }
        .test-result {
            margin: 15px 0;
            padding: 15px;
            border-left: 4px solid #bdc3c7;
            background: #ffffff;
            border-radius: 0 5px 5px 0;
        }
        .test-result.passed { border-left-color: #27ae60; }
        .test-result.failed { border-left-color: #e74c3c; }
        .test-result.error { border-left-color: #f39c12; }
        .test-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .test-name {
            margin: 0;
            color: #2c3e50;
        }
        .test-status {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
        }
        .test-status.passed { background: #d5f4e6; color: #27ae60; }
        .test-status.failed { background: #fadbd8; color: #e74c3c; }
        .test-status.error { background: #fdeaa7; color: #f39c12; }
        .failure-details {
            margin-top: 10px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 5px;
        }
        .failure-message, .traceback {
            background: #2c3e50;
            color: #ecf0f1;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        .suggestions {
            margin-top: 15px;
        }
        .suggestion {
            margin: 10px 0;
            padding: 10px;
            border-radius: 5px;
            background: #f8f9fa;
        }
        .suggestion.high { border-left: 4px solid #27ae60; }
        .suggestion.medium { border-left: 4px solid #f39c12; }
        .suggestion.low { border-left: 4px solid #e74c3c; }
        .confidence {
            font-weight: bold;
            font-size: 0.9em;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            text-align: center;
            color: #7f8c8d;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{title}}</h1>

        <div class="header-info">
            <p><strong>Generated:</strong> {{generation_time}}</p>
            <p><strong>Generator:</strong> Pytest Analyzer GUI</p>
        </div>

        {{statistics}}

        {{test_results}}

        {{charts_data}}

        <div class="footer">
            <p>Report generated by Pytest Analyzer GUI</p>
        </div>
    </div>
</body>
</html>
        """.strip()

    def _create_default_templates(self) -> None:
        """Create default report templates."""
        # Create default HTML template
        default_html = self.templates_dir / "default.html"
        if not default_html.exists():
            default_html.write_text(self._get_default_html_template(), encoding="utf-8")
            logger.info(f"Created default HTML template: {default_html}")


class ReportGeneratorWorker(QThread):
    """Worker thread for generating reports without blocking the UI."""

    progress = Signal(int)
    finished = Signal(str, bool)  # file_path, success
    error = Signal(str)

    def __init__(
        self,
        generator: ReportGenerator,
        test_results: List[TestResult],
        config: ReportConfig,
        session_data: Optional[SessionData] = None,
    ):
        super().__init__()
        self.generator = generator
        self.test_results = test_results
        self.config = config
        self.session_data = session_data

    def run(self):
        """Run the report generation in a separate thread."""
        try:
            self.progress.emit(10)

            # Generate the report
            output_file = self.generator.generate_report(
                self.test_results, self.config, self.session_data
            )

            self.progress.emit(100)
            self.finished.emit(output_file, True)

        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit("", False)
