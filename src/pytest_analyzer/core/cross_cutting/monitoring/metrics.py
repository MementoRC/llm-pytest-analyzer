from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.multiprocess import MultiProcessCollector


class ApplicationMetrics:
    """
    A centralized class for managing and exposing application metrics using Prometheus.

    This class encapsulates all metric definitions and provides a single point of access
    for metric collection. It uses a dedicated registry to avoid conflicts with other
    parts of the application or third-party libraries that might use the global
    Prometheus registry.
    """

    def __init__(self, multiprocess_dir: str = None):
        """
        Initializes the ApplicationMetrics, creating a new registry and defining all metrics.
        """
        self.registry = CollectorRegistry()
        if multiprocess_dir:
            MultiProcessCollector(self.registry)

        self._initialize_business_metrics()
        self._initialize_technical_metrics()
        self._initialize_performance_metrics()
        self._initialize_security_metrics()

    def _initialize_business_metrics(self):
        """Initializes metrics related to business logic and user interaction."""
        self.analyses_started = Counter(
            "pytest_analyzer_analyses_started_total",
            "Total number of analyses started.",
            registry=self.registry,
        )
        self.analyses_completed = Counter(
            "pytest_analyzer_analyses_completed_total",
            "Total number of analyses successfully completed.",
            ["result"],  # e.g., 'found_suggestion', 'no_suggestion'
            registry=self.registry,
        )
        self.suggestions_provided = Counter(
            "pytest_analyzer_suggestions_provided_total",
            "Total number of fix suggestions provided.",
            ["confidence"],  # e.g., 'high', 'medium', 'low'
            registry=self.registry,
        )
        self.fixes_applied = Counter(
            "pytest_analyzer_fixes_applied_total",
            "Total number of fixes applied by the user.",
            registry=self.registry,
        )

    def _initialize_technical_metrics(self):
        """Initializes metrics related to technical operations and system health."""
        self.errors_total = Counter(
            "pytest_analyzer_errors_total",
            "Total number of unexpected errors.",
            ["error_type"],  # e.g., 'ConfigurationError', 'TaskExecutionError'
            registry=self.registry,
        )
        self.llm_api_calls = Counter(
            "pytest_analyzer_llm_api_calls_total",
            "Total number of calls made to the LLM API.",
            ["model_name"],
            registry=self.registry,
        )
        self.llm_api_errors = Counter(
            "pytest_analyzer_llm_api_errors_total",
            "Total number of errors from the LLM API.",
            ["model_name", "error_code"],
            registry=self.registry,
        )
        self.cache_hits = Counter(
            "pytest_analyzer_cache_hits_total",
            "Total number of cache hits.",
            ["cache_name"],
            registry=self.registry,
        )
        self.cache_misses = Counter(
            "pytest_analyzer_cache_misses_total",
            "Total number of cache misses.",
            ["cache_name"],
            registry=self.registry,
        )

    def _initialize_performance_metrics(self):
        """Initializes metrics related to application performance."""
        self.analysis_duration = Histogram(
            "pytest_analyzer_analysis_duration_seconds",
            "Histogram of analysis duration in seconds.",
            ["result"],
            registry=self.registry,
        )
        self.llm_request_latency = Histogram(
            "pytest_analyzer_llm_request_latency_seconds",
            "Histogram of LLM API request latency in seconds.",
            ["model_name"],
            registry=self.registry,
        )
        self.active_analyses = Gauge(
            "pytest_analyzer_active_analyses",
            "Number of currently active analyses.",
            registry=self.registry,
        )

    def _initialize_security_metrics(self):
        """Initializes metrics related to security aspects."""
        self.sensitive_data_masked = Counter(
            "pytest_analyzer_sensitive_data_masked_total",
            "Total number of times sensitive data was masked.",
            registry=self.registry,
        )
        self.vault_access_errors = Counter(
            "pytest_analyzer_vault_access_errors_total",
            "Total number of errors when accessing the vault.",
            registry=self.registry,
        )

    def get_metrics_export(self) -> bytes:
        """
        Generates the latest metrics data in Prometheus text format.
        Uses the instance-specific registry.
        """
        return generate_latest(self.registry)


# Global instance for easy access, assuming a singleton-like usage pattern.
# In a more complex application, this might be managed by a dependency injection framework.
# Note: If multiple instances are created, they will have separate registries.
metrics = ApplicationMetrics()
