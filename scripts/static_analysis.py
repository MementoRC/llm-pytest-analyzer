#!/usr/bin/env python3
"""
Comprehensive Static Analysis Script for pytest-analyzer
Runs security scanning, complexity analysis, dead code detection, and more.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Ensure we're in the project root
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)


def run_command(
    cmd: List[str], capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, capture_output=capture_output, text=True, cwd=PROJECT_ROOT
        )
        return result
    except Exception as e:
        print(f"Error running command {' '.join(cmd)}: {e}")
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def run_security_scan() -> Dict[str, Any]:
    """Run Bandit security scanning."""
    print("\n=== Security Scanning with Bandit ===")

    # Try JSON output first
    result = run_command(
        ["python", "-m", "bandit", "-r", "src/", "-f", "json", "-c", ".bandit"]
    )

    security_report = {
        "tool": "bandit",
        "status": "success" if result.returncode == 0 else "failed",
        "return_code": result.returncode,
        "issues": [],
        "summary": {},
    }

    if result.returncode == 0:
        try:
            bandit_data = json.loads(result.stdout)
            security_report["issues"] = bandit_data.get("results", [])
            security_report["summary"] = {
                "total_issues": len(bandit_data.get("results", [])),
                "confidence_high": len(
                    [
                        r
                        for r in bandit_data.get("results", [])
                        if r.get("issue_confidence") == "HIGH"
                    ]
                ),
                "confidence_medium": len(
                    [
                        r
                        for r in bandit_data.get("results", [])
                        if r.get("issue_confidence") == "MEDIUM"
                    ]
                ),
                "severity_high": len(
                    [
                        r
                        for r in bandit_data.get("results", [])
                        if r.get("issue_severity") == "HIGH"
                    ]
                ),
                "severity_medium": len(
                    [
                        r
                        for r in bandit_data.get("results", [])
                        if r.get("issue_severity") == "MEDIUM"
                    ]
                ),
            }
        except json.JSONDecodeError:
            security_report["raw_output"] = result.stdout
    else:
        security_report["error"] = result.stderr or result.stdout

    # Also run console output for immediate feedback
    run_command(
        ["python", "-m", "bandit", "-r", "src/", "-c", ".bandit"], capture_output=False
    )

    return security_report


def run_complexity_analysis() -> Dict[str, Any]:
    """Run Radon complexity analysis."""
    print("\n=== Complexity Analysis with Radon ===")

    result = run_command(
        ["python", "-m", "radon", "cc", "src/", "--json", "--min", "B"]
    )

    complexity_report = {
        "tool": "radon",
        "status": "success" if result.returncode == 0 else "failed",
        "return_code": result.returncode,
        "complex_functions": [],
        "summary": {},
    }

    if result.returncode == 0:
        try:
            radon_data = json.loads(result.stdout)
            all_functions = []
            for file_path, functions in radon_data.items():
                for func in functions:
                    func["file"] = file_path
                    all_functions.append(func)

            complexity_report["complex_functions"] = all_functions
            complexity_report["summary"] = {
                "total_functions": len(all_functions),
                "grade_a": len([f for f in all_functions if f.get("rank") == "A"]),
                "grade_b": len([f for f in all_functions if f.get("rank") == "B"]),
                "grade_c": len([f for f in all_functions if f.get("rank") == "C"]),
                "grade_d": len([f for f in all_functions if f.get("rank") == "D"]),
                "grade_f": len([f for f in all_functions if f.get("rank") == "F"]),
            }
        except json.JSONDecodeError:
            complexity_report["raw_output"] = result.stdout
    else:
        complexity_report["error"] = result.stderr or result.stdout

    # Console output
    run_command(
        ["python", "-m", "radon", "cc", "src/", "--min", "B"], capture_output=False
    )

    return complexity_report


def run_dead_code_detection() -> Dict[str, Any]:
    """Run Vulture dead code detection."""
    print("\n=== Dead Code Detection with Vulture ===")

    result = run_command(["python", "-m", "vulture", "src/", "--min-confidence", "80"])

    dead_code_report = {
        "tool": "vulture",
        "status": "success" if result.returncode == 0 else "failed",
        "return_code": result.returncode,
        "raw_output": result.stdout,
        "summary": {},
    }

    # Parse vulture output (it's text-based)
    if result.stdout:
        lines = result.stdout.strip().split("\n")
        dead_code_items = [
            line for line in lines if line.strip() and not line.startswith("#")
        ]
        dead_code_report["summary"] = {
            "potential_dead_code_items": len(dead_code_items),
            "items": dead_code_items,
        }

    return dead_code_report


def run_dependency_security_check() -> Dict[str, Any]:
    """Run Safety dependency security check."""
    print("\n=== Dependency Security Check with Safety ===")

    result = run_command(["python", "-m", "safety", "check", "--json"])

    safety_report = {
        "tool": "safety",
        "status": "success" if result.returncode == 0 else "failed",
        "return_code": result.returncode,
        "vulnerabilities": [],
        "summary": {},
    }

    if result.returncode == 0:
        safety_report["summary"]["vulnerabilities_found"] = 0
    else:
        try:
            if result.stdout:
                safety_data = json.loads(result.stdout)
                safety_report["vulnerabilities"] = safety_data
                safety_report["summary"]["vulnerabilities_found"] = len(safety_data)
        except json.JSONDecodeError:
            safety_report["raw_output"] = result.stdout
            safety_report["error"] = result.stderr

    # Console output for immediate feedback
    run_command(
        ["python", "-m", "safety", "check"], capture_output=False
    )

    return safety_report


def run_pylint_analysis() -> Dict[str, Any]:
    """Run Pylint code quality analysis."""
    print("\n=== Code Quality Analysis with Pylint ===")

    result = run_command(
        ["python", "-m", "pylint", "src/pytest_analyzer", "--output-format=json"]
    )

    pylint_report = {
        "tool": "pylint",
        "status": "success" if result.returncode == 0 else "failed",
        "return_code": result.returncode,
        "issues": [],
        "summary": {},
    }

    try:
        if result.stdout:
            pylint_data = json.loads(result.stdout)
            pylint_report["issues"] = pylint_data

            # Categorize issues
            error_count = len([i for i in pylint_data if i.get("type") == "error"])
            warning_count = len([i for i in pylint_data if i.get("type") == "warning"])
            convention_count = len(
                [i for i in pylint_data if i.get("type") == "convention"]
            )
            refactor_count = len(
                [i for i in pylint_data if i.get("type") == "refactor"]
            )

            pylint_report["summary"] = {
                "total_issues": len(pylint_data),
                "errors": error_count,
                "warnings": warning_count,
                "conventions": convention_count,
                "refactor": refactor_count,
            }
    except json.JSONDecodeError:
        pylint_report["raw_output"] = result.stdout
        pylint_report["error"] = result.stderr

    return pylint_report


def generate_consolidated_report(reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a consolidated analysis report."""
    consolidated = {
        "timestamp": datetime.now().isoformat(),
        "project": "pytest-analyzer",
        "analysis_type": "comprehensive_static_analysis",
        "summary": {
            "total_tools_run": len(reports),
            "tools_succeeded": len(
                [r for r in reports.values() if r.get("status") == "success"]
            ),
            "tools_failed": len(
                [r for r in reports.values() if r.get("status") == "failed"]
            ),
        },
        "security": {
            "high_severity_issues": 0,
            "medium_severity_issues": 0,
            "dependency_vulnerabilities": 0,
        },
        "quality": {
            "complex_functions": 0,
            "dead_code_items": 0,
            "pylint_errors": 0,
            "pylint_warnings": 0,
        },
        "details": reports,
    }

    # Extract key metrics
    if "security" in reports:
        security = reports["security"].get("summary", {})
        consolidated["security"]["high_severity_issues"] = security.get(
            "severity_high", 0
        )
        consolidated["security"]["medium_severity_issues"] = security.get(
            "severity_medium", 0
        )

    if "safety" in reports:
        consolidated["security"]["dependency_vulnerabilities"] = (
            reports["safety"].get("summary", {}).get("vulnerabilities_found", 0)
        )

    if "complexity" in reports:
        complexity = reports["complexity"].get("summary", {})
        consolidated["quality"]["complex_functions"] = (
            complexity.get("grade_c", 0)
            + complexity.get("grade_d", 0)
            + complexity.get("grade_f", 0)
        )

    if "dead_code" in reports:
        consolidated["quality"]["dead_code_items"] = (
            reports["dead_code"].get("summary", {}).get("potential_dead_code_items", 0)
        )

    if "pylint" in reports:
        pylint_summary = reports["pylint"].get("summary", {})
        consolidated["quality"]["pylint_errors"] = pylint_summary.get("errors", 0)
        consolidated["quality"]["pylint_warnings"] = pylint_summary.get("warnings", 0)

    return consolidated


def main():
    """Main analysis workflow."""
    print("🔍 Starting Comprehensive Static Analysis for pytest-analyzer")
    print(f"📁 Project root: {PROJECT_ROOT}")

    # Ensure analysis output directory exists
    output_dir = PROJECT_ROOT / "analysis_reports"
    output_dir.mkdir(exist_ok=True)

    # Run all analysis tools
    reports = {}

    try:
        reports["security"] = run_security_scan()
    except Exception as e:
        print(f"Security scan failed: {e}")
        reports["security"] = {"tool": "bandit", "status": "failed", "error": str(e)}

    try:
        reports["complexity"] = run_complexity_analysis()
    except Exception as e:
        print(f"Complexity analysis failed: {e}")
        reports["complexity"] = {"tool": "radon", "status": "failed", "error": str(e)}

    try:
        reports["dead_code"] = run_dead_code_detection()
    except Exception as e:
        print(f"Dead code detection failed: {e}")
        reports["dead_code"] = {"tool": "vulture", "status": "failed", "error": str(e)}

    try:
        reports["safety"] = run_dependency_security_check()
    except Exception as e:
        print(f"Dependency security check failed: {e}")
        reports["safety"] = {"tool": "safety", "status": "failed", "error": str(e)}

    try:
        reports["pylint"] = run_pylint_analysis()
    except Exception as e:
        print(f"Pylint analysis failed: {e}")
        reports["pylint"] = {"tool": "pylint", "status": "failed", "error": str(e)}

    # Generate consolidated report
    consolidated_report = generate_consolidated_report(reports)

    # Save reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"static_analysis_report_{timestamp}.json"

    with open(report_file, "w") as f:
        json.dump(consolidated_report, f, indent=2)

    print(f"\n📊 Analysis complete! Report saved to: {report_file}")

    # Print summary
    print("\n=== ANALYSIS SUMMARY ===")
    print(
        f"🔒 Security Issues (High): {consolidated_report['security']['high_severity_issues']}"
    )
    print(
        f"🔒 Security Issues (Medium): {consolidated_report['security']['medium_severity_issues']}"
    )
    print(
        f"🔒 Dependency Vulnerabilities: {consolidated_report['security']['dependency_vulnerabilities']}"
    )
    print(
        f"📊 Complex Functions: {consolidated_report['quality']['complex_functions']}"
    )
    print(f"💀 Dead Code Items: {consolidated_report['quality']['dead_code_items']}")
    print(f"⚠️  Pylint Errors: {consolidated_report['quality']['pylint_errors']}")
    print(f"⚠️  Pylint Warnings: {consolidated_report['quality']['pylint_warnings']}")

    # Return exit code based on critical issues
    critical_issues = (
        consolidated_report["security"]["high_severity_issues"]
        + consolidated_report["security"]["dependency_vulnerabilities"]
        + consolidated_report["quality"]["pylint_errors"]
    )

    if critical_issues > 0:
        print(
            f"\n❌ Found {critical_issues} critical issues that need immediate attention!"
        )
        return 1
    else:
        print("\n✅ No critical issues found!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
