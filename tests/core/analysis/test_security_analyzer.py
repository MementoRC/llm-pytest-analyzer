import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.pytest_analyzer.core.analysis.security_analyzer import SecurityAnalyzer
from src.pytest_analyzer.core.domain.entities.fix_suggestion import FixSuggestion
from src.pytest_analyzer.core.domain.value_objects.suggestion_confidence import (
    SuggestionConfidence,
)
from src.pytest_analyzer.utils.config_types import SecuritySettings

# --- Fixtures ---


@pytest.fixture
def tmp_project_root(tmp_path):
    """Creates a temporary project root with some dummy files."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "app.py").write_text("print('hello')\npassword = 'mysecret'")
    (root / "tests" / "test_security.py").write_text(
        """
import os
import tempfile
import subprocess

def test_hardcoded_secret():
    api_key = "supersecretkey123" # nosec
    assert True

def test_os_system():
    os.system("echo hello")

def test_insecure_temp_file():
    tmp_file = tempfile.mktemp()
    with open(tmp_file, "w") as f:
        f.write("data")

def test_subprocess_check_false():
    subprocess.run(["ls", "-l"], check=False)

def test_safe_subprocess():
    subprocess.run(["echo", "safe"], check=True)

def test_path_concat():
    base_path = "/tmp"
    file_name = "data.txt"
    full_path = base_path + "/" + file_name # nosec
    assert True
"""
    )
    (root / "requirements.txt").write_text("requests==2.25.1\ndjango==3.2.0")
    return root


@pytest.fixture
def mock_security_settings():
    """Provides mock security settings."""
    return SecuritySettings(
        path_allowlist=[],
        allowed_file_types=[],
        max_file_size_mb=10.0,
        enable_input_sanitization=True,
        restrict_to_project_dir=True,
        enable_backup=True,
        require_authentication=True,
        auth_token="test_token",
        require_client_certificate=False,
        allowed_client_certs=[],
        role_based_access=False,
        allowed_roles=set(),
        max_requests_per_window=10,
        rate_limit_window_seconds=60,
        abuse_threshold=5,
        abuse_ban_count=1,
        max_resource_usage_mb=100.0,
        enable_resource_usage_monitoring=True,
        enable_circuit_breaker=True,
        circuit_breaker_failures=3,
        circuit_breaker_timeout_seconds=30,
        circuit_breaker_successes_to_close=2,
        llm_rate_limit=None,
        per_tool_rate_limits={},
    )


@pytest.fixture
def security_analyzer(tmp_project_root, mock_security_settings):
    """Provides a SecurityAnalyzer instance."""
    return SecurityAnalyzer(tmp_project_root, mock_security_settings)


@pytest.fixture
def mock_subprocess_run():
    """Mocks subprocess.run for external tool calls."""
    with patch("subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture
def mock_shutil_which():
    """Mocks shutil.which for tool availability checks."""
    with patch("shutil.which") as mock_which:
        yield mock_which


# --- Tests for SecurityAnalyzer ---


def test_security_analyzer_init(tmp_project_root, mock_security_settings):
    analyzer = SecurityAnalyzer(tmp_project_root, mock_security_settings)
    assert analyzer.project_root == tmp_project_root
    assert analyzer.settings == mock_security_settings


def test_security_analyzer_init_invalid_path():
    with pytest.raises(ValueError, match="Project root must be a valid directory"):
        SecurityAnalyzer("/non/existent/path", MagicMock())


@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._run_subprocess"
)
@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._is_tool_available"
)
def test_run_static_analysis_success(
    mock_is_tool_available, mock_run_subprocess, security_analyzer, tmp_project_root
):
    mock_is_tool_available.return_value = True
    mock_run_subprocess.return_value = (
        True,
        json.dumps(
            {
                "results": [
                    {
                        "issue_severity": "HIGH",
                        "issue_confidence": "HIGH",
                        "issue_text": "Hardcoded password",
                        "code": "password = 'mysecret'",
                        "filename": str(tmp_project_root / "src" / "app.py"),
                        "line_number": 2,
                        "test_name": "B105",
                    }
                ]
            }
        ),
    )

    findings = security_analyzer._run_static_analysis(tmp_project_root)
    assert len(findings) == 1
    assert findings[0]["source"] == "Bandit"
    assert findings[0]["severity"] == "HIGH"
    assert "Hardcoded password" in findings[0]["message"]
    assert findings[0]["fix_suggestion"] is not None
    assert "Replace hardcoded password" in findings[0]["fix_suggestion"].suggestion_text


@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._run_subprocess"
)
@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._is_tool_available"
)
def test_run_static_analysis_bandit_not_available(
    mock_is_tool_available, mock_run_subprocess, security_analyzer, tmp_project_root
):
    mock_is_tool_available.return_value = False
    findings = security_analyzer._run_static_analysis(tmp_project_root)
    assert len(findings) == 1
    assert (
        findings[0]["source"] == "PolicyViolation"
    )  # ToolMissing is a policy violation
    assert "Bandit static analysis tool not found" in findings[0]["message"]
    mock_run_subprocess.assert_not_called()


@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._run_subprocess"
)
@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._is_tool_available"
)
def test_run_static_analysis_bandit_failure(
    mock_is_tool_available, mock_run_subprocess, security_analyzer, tmp_project_root
):
    mock_is_tool_available.return_value = True
    mock_run_subprocess.return_value = (False, "Bandit failed for some reason")
    findings = security_analyzer._run_static_analysis(tmp_project_root)
    assert len(findings) == 1
    assert (
        findings[0]["source"] == "PolicyViolation"
    )  # BanditError is an internal finding
    assert "Bandit scan failed" in findings[0]["message"]


@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._run_subprocess"
)
@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._is_tool_available"
)
def test_run_dependency_scan_success(
    mock_is_tool_available, mock_run_subprocess, security_analyzer
):
    mock_is_tool_available.return_value = True
    mock_run_subprocess.return_value = (
        True,
        json.dumps(
            [
                {
                    "package_name": "requests",
                    "vulnerable_specifier": "==2.25.1",
                    "fix_version": "2.26.0",
                    "advisory": "Requests has a vulnerability",
                    "cve": "CVE-2021-1234",
                }
            ]
        ),
    )

    findings = security_analyzer._run_dependency_scan()
    assert len(findings) == 1
    assert findings[0]["source"] == "Safety"
    assert findings[0]["severity"] == "High"
    assert "Requests has a vulnerability" in findings[0]["message"]
    assert findings[0]["package"] == "requests"
    assert findings[0]["fix_suggestion"] is not None
    assert "Update package 'requests'" in findings[0]["fix_suggestion"].suggestion_text


@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._run_subprocess"
)
@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._is_tool_available"
)
def test_run_dependency_scan_safety_not_available(
    mock_is_tool_available, mock_run_subprocess, security_analyzer
):
    mock_is_tool_available.return_value = False
    findings = security_analyzer._run_dependency_scan()
    assert len(findings) == 1
    assert findings[0]["source"] == "PolicyViolation"
    assert "Safety dependency vulnerability scanner not found" in findings[0]["message"]
    mock_run_subprocess.assert_not_called()


@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._run_subprocess"
)
@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._is_tool_available"
)
def test_run_dependency_scan_safety_failure(
    mock_is_tool_available, mock_run_subprocess, security_analyzer
):
    mock_is_tool_available.return_value = True
    mock_run_subprocess.return_value = (False, "Safety failed for some reason")
    findings = security_analyzer._run_dependency_scan()
    assert len(findings) == 1
    assert findings[0]["source"] == "PolicyViolation"
    assert "Safety scan failed" in findings[0]["message"]


def test_analyze_test_code_for_patterns(security_analyzer, tmp_project_root):
    test_file = tmp_project_root / "tests" / "test_security.py"
    findings = security_analyzer._analyze_test_code_for_patterns([test_file])

    # Expecting findings for hardcoded_secret, os_system_usage, insecure_temp_file, subprocess_without_check, direct_path_manipulation
    assert len(findings) == 5

    # Check for specific findings
    hardcoded_secret_found = any(
        f["type"] == "hardcoded_secret" and "api_key" in f["code_snippet"]
        for f in findings
    )
    os_system_found = any(
        f["type"] == "os_system_usage" and "os.system" in f["code_snippet"]
        for f in findings
    )
    insecure_temp_file_found = any(
        f["type"] == "insecure_temp_file" and "tempfile.mktemp" in f["code_snippet"]
        for f in findings
    )
    subprocess_check_false_found = any(
        f["type"] == "subprocess_without_check" and "check=False" in f["code_snippet"]
        for f in findings
    )
    path_concat_found = any(
        f["type"] == "direct_path_manipulation"
        and 'base_path + "/" + file_name' in f["code_snippet"]
        for f in findings
    )

    assert hardcoded_secret_found
    assert os_system_found
    assert insecure_temp_file_found
    assert subprocess_check_false_found
    assert path_concat_found

    # Verify relative path and line number
    secret_finding = next(f for f in findings if f["type"] == "hardcoded_secret")
    assert secret_finding["filename"] == str(Path("tests") / "test_security.py")
    assert secret_finding["line_number"] == 7  # api_key line in the test file


def test_analyze_test_code_for_patterns_no_test_files(security_analyzer, tmp_path):
    findings = security_analyzer._analyze_test_code_for_patterns([])
    assert len(findings) == 0


def test_validate_security_policy_success(security_analyzer):
    # Default settings should pass this specific policy check
    findings = security_analyzer._validate_security_policy()
    assert len(findings) == 0


def test_validate_security_policy_auth_token_missing(tmp_project_root):
    settings = SecuritySettings(
        require_authentication=True,
        auth_token=None,  # Missing token
        enable_resource_usage_monitoring=True,
        max_resource_usage_mb=10.0,
    )
    analyzer = SecurityAnalyzer(tmp_project_root, settings)
    findings = analyzer._validate_security_policy()
    assert len(findings) == 1
    assert findings[0]["type"] == "PolicyViolation"
    assert "no auth_token is set" in findings[0]["message"]


def test_validate_security_policy_resource_usage_zero(
    tmp_project_root, mock_security_settings
):
    # Manually override the setting after creation to test the validation logic
    mock_security_settings.enable_resource_usage_monitoring = True
    mock_security_settings.max_resource_usage_mb = 0.0
    analyzer = SecurityAnalyzer(tmp_project_root, mock_security_settings)
    findings = analyzer._validate_security_policy()
    assert len(findings) == 1
    assert findings[0]["type"] == "PolicyViolation"
    assert "max_resource_usage_mb is not set or is zero" in findings[0]["message"]


def test_calculate_security_score():
    analyzer = SecurityAnalyzer(Path("."), MagicMock())  # Dummy init

    # No findings
    score = analyzer.calculate_security_score([])
    assert score == 100.0

    # Mixed findings
    findings = [
        {"severity": "Critical"},  # -20
        {"severity": "High"},  # -10
        {"severity": "Medium"},  # -5
        {"severity": "Low"},  # -2
        {"severity": "Unknown"},  # -0
    ]
    score = analyzer.calculate_security_score(findings)
    assert score == 100 - 20 - 10 - 5 - 2
    assert score == 63.0

    # Score cannot go below zero
    many_critical_findings = [{"severity": "Critical"} for _ in range(10)]
    score = analyzer.calculate_security_score(many_critical_findings)
    assert score == 0.0


def test_generate_secure_coding_guidelines(security_analyzer):
    guidelines = security_analyzer.generate_secure_coding_guidelines()
    assert isinstance(guidelines, list)
    assert len(guidelines) > 5  # Ensure a reasonable number of guidelines
    assert "Always sanitize external inputs" in guidelines[0]
    assert "Avoid hardcoding sensitive information" in guidelines[1]


def test_suggest_security_patch_bandit_b105(security_analyzer):
    finding = {
        "source": "Bandit",
        "issue_severity": "HIGH",
        "issue_confidence": "HIGH",
        "issue_text": "A hardcoded password has been identified.",
        "code": "password = 'mysecret'",
        "filename": "src/app.py",
        "line_number": 2,
        "test_name": "B105",
    }
    suggestion = security_analyzer.suggest_security_patch(finding)
    assert isinstance(suggestion, FixSuggestion)
    assert "Replace hardcoded password" in suggestion.suggestion_text
    assert suggestion.confidence == SuggestionConfidence.HIGH


def test_suggest_security_patch_safety(security_analyzer):
    finding = {
        "source": "Safety",
        "package": "django",
        "vulnerable_version": "==3.2.0",
        "fix_version": "3.2.10",
        "advisory": "Django has a SQL injection vulnerability.",
        "CVE": "CVE-2021-5678",
    }
    suggestion = security_analyzer.suggest_security_patch(finding)
    assert isinstance(suggestion, FixSuggestion)
    assert (
        "Update package 'django' to a version >= 3.2.10" in suggestion.suggestion_text
    )
    assert suggestion.confidence == SuggestionConfidence.HIGH


def test_suggest_security_patch_test_pattern_os_system(security_analyzer):
    finding = {
        "source": "TestPattern",
        "type": "os_system_usage",
        "message": "Usage of os.system detected.",
        "severity": "Medium",
        "code_snippet": 'os.system("echo hello")',
        "filename": "tests/test_security.py",
        "line_number": 8,
    }
    suggestion = security_analyzer.suggest_security_patch(finding)
    assert isinstance(suggestion, FixSuggestion)
    assert "Replace os.system with subprocess.run" in suggestion.suggestion_text
    assert suggestion.confidence == SuggestionConfidence.MEDIUM


def test_suggest_security_patch_unknown_finding(security_analyzer):
    finding = {"source": "Unknown", "type": "SomeNewIssue", "message": "New issue."}
    suggestion = security_analyzer.suggest_security_patch(finding)
    assert suggestion is None


@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._run_static_analysis"
)
@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._run_dependency_scan"
)
@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._analyze_test_code_for_patterns"
)
@patch(
    "src.pytest_analyzer.core.analysis.security_analyzer.SecurityAnalyzer._validate_security_policy"
)
def test_analyze_project_security_orchestration(
    mock_validate_policy,
    mock_analyze_patterns,
    mock_run_dependency_scan,
    mock_run_static_analysis,
    security_analyzer,
):
    mock_run_static_analysis.return_value = [{"source": "Bandit", "severity": "High"}]
    mock_run_dependency_scan.return_value = [
        {"source": "Safety", "severity": "Critical"}
    ]
    mock_analyze_patterns.return_value = [
        {"source": "TestPattern", "type": "hardcoded_secret", "severity": "High"}
    ]
    mock_validate_policy.return_value = []

    report = security_analyzer.analyze_project_security()

    mock_run_static_analysis.assert_called_once()
    mock_run_dependency_scan.assert_called_once()
    mock_analyze_patterns.assert_called_once()
    mock_validate_policy.assert_called_once()

    assert report["total_findings"] == 3
    assert report["security_score"] == pytest.approx(
        100 - 10 - 20 - 10
    )  # High, Critical, High
    assert any(f["source"] == "Bandit" for f in report["findings"])
    assert any(f["source"] == "Safety" for f in report["findings"])
    assert any(f["source"] == "TestPattern" for f in report["findings"])
    assert report["summary"]["findings_by_severity"]["High"] == 2
    assert report["summary"]["findings_by_severity"]["Critical"] == 1


def test_run_subprocess_success(security_analyzer, mock_subprocess_run):
    mock_subprocess_run.return_value = MagicMock(
        returncode=0, stdout="Success", stderr=""
    )
    success, output = security_analyzer._run_subprocess(["echo", "hello"])
    assert success is True
    assert output == "Success"


def test_run_subprocess_failure(security_analyzer, mock_subprocess_run):
    mock_subprocess_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="Error"
    )
    success, output = security_analyzer._run_subprocess(["bad_command"])
    assert success is False
    assert output == "\nError"


def test_run_subprocess_file_not_found(security_analyzer, mock_subprocess_run):
    mock_subprocess_run.side_effect = FileNotFoundError
    success, output = security_analyzer._run_subprocess(["non_existent_tool"])
    assert success is False
    assert "Tool not found" in output


def test_get_pixi_env_exists(security_analyzer, tmp_project_root):
    pixi_bin_path = tmp_project_root / ".pixi/env/bin"
    pixi_bin_path.mkdir(parents=True)
    (pixi_bin_path / "python").touch()  # Simulate an executable

    env = security_analyzer._get_pixi_env()
    assert env is not None
    assert str(pixi_bin_path) in env["PATH"]


def test_get_pixi_env_not_exists(security_analyzer, tmp_project_root):
    env = security_analyzer._get_pixi_env()
    assert env is None


def test_is_tool_available_shutil_which(security_analyzer, mock_shutil_which):
    mock_shutil_which.return_value = "/usr/bin/bandit"
    assert security_analyzer._is_tool_available("bandit", None) is True
    mock_shutil_which.assert_called_once_with("bandit")


def test_is_tool_available_env_path(security_analyzer, mock_shutil_which, tmp_path):
    mock_shutil_which.return_value = None  # shutil.which doesn't find it
    custom_bin = tmp_path / "custom_bin"
    custom_bin.mkdir()
    (custom_bin / "mytool").touch()
    custom_env = {"PATH": str(custom_bin)}

    assert security_analyzer._is_tool_available("mytool", custom_env) is True
    mock_shutil_which.assert_called_once_with("mytool")


def test_is_tool_available_not_found(security_analyzer, mock_shutil_which):
    mock_shutil_which.return_value = None
    assert security_analyzer._is_tool_available("nonexistent", None) is False
    mock_shutil_which.assert_called_once_with("nonexistent")
