from pathlib import Path

# --- Mocks and stubs for the advanced skip marker system ---


class SkipCondition:
    def __init__(self, name, evaluator, reason=None):
        self.name = name
        self.evaluator = evaluator
        self.reason = reason or f"Condition '{name}' met"

    def evaluate(self, context):
        return self.evaluator(context)

    def natural_language_reason(self, context):
        if callable(self.reason):
            return self.reason(context)
        return self.reason


class SkipMarkerGenerator:
    def __init__(self):
        self.conditions = []

    def add_condition(self, condition: SkipCondition):
        self.conditions.append(condition)

    def generate_marker(self, context):
        reasons = [
            cond.natural_language_reason(context)
            for cond in self.conditions
            if cond.evaluate(context)
        ]
        if not reasons:
            return None
        # Conflict resolution: merge reasons, deduplicate
        reasons = list(dict.fromkeys(reasons))
        return f'@pytest.mark.skip(reason="{" | ".join(reasons)}")'


class SkipSuggestionSystem:
    def __init__(self, marker_generator):
        self.marker_generator = marker_generator

    def suggest_skip(self, context):
        return self.marker_generator.generate_marker(context)


class SkipTracker:
    def __init__(self):
        self.history = {}

    def record_skip(self, test_name):
        self.history.setdefault(test_name, 0)
        self.history[test_name] += 1

    def get_skip_count(self, test_name):
        return self.history.get(test_name, 0)


class SkipAnalytics:
    def __init__(self, tracker):
        self.tracker = tracker

    def frequently_skipped(self, threshold=3):
        return [
            name for name, count in self.tracker.history.items() if count >= threshold
        ]

    def alert_for_frequent_skips(self, threshold=3):
        frequent = self.frequently_skipped(threshold)
        if frequent:
            return f"ALERT: Frequently skipped tests: {', '.join(frequent)}"
        return None


# --- Integration stub for TestCategorizer ---
class DummyTestCategorizer:
    def generate_skip_marker(self, test_file: Path, reason: str) -> str:
        return f'@pytest.mark.skip(reason="{reason}")'


# --- TESTS ---


def test_skip_condition_creation_and_evaluation():
    context = {"os": "linux", "ci": True}
    cond = SkipCondition(
        "LinuxOnly", lambda ctx: ctx["os"] == "linux", "Linux environment"
    )
    assert cond.evaluate(context) is True
    assert cond.natural_language_reason(context) == "Linux environment"

    cond2 = SkipCondition("NotCI", lambda ctx: not ctx["ci"])
    assert cond2.evaluate(context) is False
    assert cond2.natural_language_reason(context) == "Condition 'NotCI' met"


def test_skip_marker_generation_various_conditions():
    context = {"os": "windows", "ci": True}
    gen = SkipMarkerGenerator()
    gen.add_condition(
        SkipCondition(
            "Windows", lambda ctx: ctx["os"] == "windows", "Windows not supported"
        )
    )
    gen.add_condition(SkipCondition("CI", lambda ctx: ctx["ci"], "Running in CI"))
    marker = gen.generate_marker(context)
    assert marker == '@pytest.mark.skip(reason="Windows not supported | Running in CI")'

    # No conditions met
    context2 = {"os": "linux", "ci": False}
    marker2 = gen.generate_marker(context2)
    assert marker2 is None


def test_natural_language_reason_generation_and_readability():
    def dynamic_reason(ctx):
        return f"Test skipped on {ctx['os']}"

    cond = SkipCondition("OS", lambda ctx: True, dynamic_reason)
    context = {"os": "macos"}
    assert cond.natural_language_reason(context) == "Test skipped on macos"


def test_conflict_resolution_with_overlapping_conditions():
    context = {"os": "linux", "ci": True}
    gen = SkipMarkerGenerator()
    # Both conditions produce the same reason
    gen.add_condition(
        SkipCondition("Linux", lambda ctx: ctx["os"] == "linux", "Linux not supported")
    )
    gen.add_condition(
        SkipCondition(
            "LinuxAgain", lambda ctx: ctx["os"] == "linux", "Linux not supported"
        )
    )
    marker = gen.generate_marker(context)
    # Should deduplicate reasons
    assert marker == '@pytest.mark.skip(reason="Linux not supported")'


def test_skip_suggestion_system_validation_with_edge_cases():
    context = {"os": "solaris", "ci": False}
    gen = SkipMarkerGenerator()
    gen.add_condition(
        SkipCondition(
            "Solaris", lambda ctx: ctx["os"] == "solaris", "Solaris not supported"
        )
    )
    suggester = SkipSuggestionSystem(gen)
    marker = suggester.suggest_skip(context)
    assert marker == '@pytest.mark.skip(reason="Solaris not supported")'

    # Edge: no conditions met
    context2 = {"os": "linux", "ci": False}
    marker2 = suggester.suggest_skip(context2)
    assert marker2 is None


def test_skip_tracking_mechanism_with_mock_test_history():
    tracker = SkipTracker()
    tracker.record_skip("test_foo")
    tracker.record_skip("test_foo")
    tracker.record_skip("test_bar")
    assert tracker.get_skip_count("test_foo") == 2
    assert tracker.get_skip_count("test_bar") == 1
    assert tracker.get_skip_count("test_baz") == 0


def test_skip_analytics_and_alerts_for_frequently_skipped_tests():
    tracker = SkipTracker()
    for _ in range(5):
        tracker.record_skip("test_flaky")
    for _ in range(2):
        tracker.record_skip("test_sometimes")
    analytics = SkipAnalytics(tracker)
    assert analytics.frequently_skipped(threshold=3) == ["test_flaky"]
    alert = analytics.alert_for_frequent_skips(threshold=3)
    assert "test_flaky" in alert

    # No alert if below threshold
    analytics2 = SkipAnalytics(SkipTracker())
    assert analytics2.alert_for_frequent_skips(threshold=2) is None


def test_integration_with_existing_test_categorizer(tmp_path):
    # Simulate integration: use DummyTestCategorizer to generate skip marker
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_example(): pass")
    categorizer = DummyTestCategorizer()
    reason = "Not supported in CI"
    marker = categorizer.generate_skip_marker(test_file, reason)
    assert marker == '@pytest.mark.skip(reason="Not supported in CI")'

    # Edge: empty reason
    marker2 = categorizer.generate_skip_marker(test_file, "")
    assert marker2 == '@pytest.mark.skip(reason="")'
