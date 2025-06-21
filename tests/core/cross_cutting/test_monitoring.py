"""Tests for monitoring functionality."""

import pytest

from pytest_analyzer.core.cross_cutting.monitoring.metrics import ApplicationMetrics


class TestApplicationMetrics:
    """Test the ApplicationMetrics class."""

    def test_metrics_initialization(self):
        """Test that all metrics are properly initialized."""
        app_metrics = ApplicationMetrics()

        # Test business metrics
        assert hasattr(app_metrics, "analyses_started")
        assert hasattr(app_metrics, "analyses_completed")
        assert hasattr(app_metrics, "suggestions_provided")
        assert hasattr(app_metrics, "fixes_applied")

        # Test technical metrics
        assert hasattr(app_metrics, "errors_total")
        assert hasattr(app_metrics, "llm_api_calls")
        assert hasattr(app_metrics, "llm_api_errors")
        assert hasattr(app_metrics, "cache_hits")

        # Test performance metrics
        assert hasattr(app_metrics, "analysis_duration")
        assert hasattr(app_metrics, "llm_request_latency")
        assert hasattr(app_metrics, "active_analyses")

        # Test security metrics
        assert hasattr(app_metrics, "sensitive_data_masked")
        assert hasattr(app_metrics, "vault_access_errors")

    def test_metrics_export(self):
        """Test metrics export functionality."""
        app_metrics = ApplicationMetrics()
        export_data = app_metrics.get_metrics_export()

        assert isinstance(export_data, bytes)
        assert len(export_data) > 0

        # Convert to string to check content
        export_str = export_data.decode("utf-8")
        assert "pytest_analyzer_analyses_started_total" in export_str

    def test_separate_instances_have_separate_registries(self):
        """Test that separate instances have independent registries."""
        metrics1 = ApplicationMetrics()
        metrics2 = ApplicationMetrics()

        # They should have different registry objects
        assert metrics1.registry is not metrics2.registry

        # Changes to one shouldn't affect the other
        metrics1.analyses_started.inc()
        export1 = metrics1.get_metrics_export().decode("utf-8")
        export2 = metrics2.get_metrics_export().decode("utf-8")

        # The first should show the increment, the second should not
        assert "1.0" in export1
        assert "0.0" in export2 or "1.0" not in export2


class TestGlobalMetricsInstance:
    """Test the global metrics instance."""

    def test_global_metrics_instance(self):
        """Test that global metrics instance is properly initialized."""
        from pytest_analyzer.core.cross_cutting.monitoring.metrics import metrics

        assert metrics is not None
        assert isinstance(metrics, ApplicationMetrics)

        # Test that we can access all metrics through global instance
        assert hasattr(metrics, "analyses_started")
        assert hasattr(metrics, "llm_api_calls")
        assert hasattr(metrics, "analysis_duration")

    def test_metrics_can_be_used(self):
        """Test that metrics can be used for basic operations."""
        from pytest_analyzer.core.cross_cutting.monitoring.metrics import metrics

        # Test counter increment
        initial_export = metrics.get_metrics_export()
        metrics.analyses_started.inc()
        after_export = metrics.get_metrics_export()

        # The export should have changed
        assert initial_export != after_export

        # Test gauge set
        metrics.active_analyses.set(5)
        export_with_gauge = metrics.get_metrics_export().decode("utf-8")
        assert "5.0" in export_with_gauge

        # Test histogram observe (requires label)
        metrics.analysis_duration.labels(result="success").observe(2.5)
        histogram_export = metrics.get_metrics_export().decode("utf-8")
        assert "analysis_duration" in histogram_export


@pytest.fixture(autouse=True)
def isolate_tests():
    """Ensure tests don't interfere with each other."""
    # This fixture runs before and after each test
    yield
    # Any cleanup needed would go here
