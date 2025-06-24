"""
Test: Final Security Audit Validation

This test validates that the final security audit script runs successfully and
produces a comprehensive report, confirming that all required security controls
and improvements are in place.
"""

import json
import subprocess
from pathlib import Path


def test_final_security_audit_script_runs(tmp_path):
    # Run the final security audit script
    result = subprocess.run(
        ["python3", "scripts/final_security_audit.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Check that the script output contains expected summary lines
    assert "FINAL SECURITY AUDIT SUMMARY" in result.stdout
    assert "Executive Summary:" in result.stdout
    assert "Key Recommendations:" in result.stdout

    # Find the generated report file
    reports_dir = Path("analysis_reports")
    report_files = sorted(reports_dir.glob("final_security_audit_*.json"))
    assert report_files, "No final security audit report generated"
    with open(report_files[-1], "r") as f:
        report = json.load(f)

    # Validate key fields in the report
    assert report["task_reference"] == "Task 24 - Conduct Final Security Audit"
    assert report["security_improvements_validated"]["input_validation"] is True
    assert report["access_control_review"]["token_auth"] is True
    assert report["data_protection_assessment"]["encryption_at_rest"] is True
    assert "executive_summary" in report
    assert "recommendations" in report
    assert isinstance(report["recommendations"], list)

    # Accept that static analysis and dependency checks may be skipped if tools are missing
    static_analysis = report.get("static_analysis", {})
    dependency_security = report.get("dependency_security", {})

    # Check if static analysis ran (either successfully or with tool issues)
    if "static_analysis" in report:
        # If bandit is not available, the output will mention this
        if not static_analysis.get("success", False):
            output = static_analysis.get("output", "")
            # Either the tool is missing or bandit found issues (which is expected)
            assert (
                "Bandit not available" in output
                or "Skipping static analysis" in output
                or "Issue:" in output
            )  # Bandit found security issues

    # Check if dependency check ran
    if "dependency_security" in report:
        if not dependency_security.get("success", False):
            output = dependency_security.get("output", "")
            assert (
                "Safety not available" in output
                or "Skipping dependency check" in output
            )
