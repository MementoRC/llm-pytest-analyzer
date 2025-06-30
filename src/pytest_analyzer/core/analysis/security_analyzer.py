"""
SecurityAnalyzer for comprehensive security analysis of tests and test infrastructure.

This module provides a dedicated class for identifying and mitigating potential
vulnerabilities within test code and the surrounding test environment. It integrates
with static analysis tools, performs dependency scanning, and applies test-specific
security checks.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ...core.domain.entities.fix_suggestion import FixSuggestion
from ...core.domain.value_objects.suggestion_confidence import SuggestionConfidence
from ...utils.config_types import SecuritySettings

logger = logging.getLogger(__name__)


class SecurityAnalyzer:
    """
    Provides comprehensive security analysis for identifying and mitigating
    potential vulnerabilities in tests and test infrastructure.

    This class is distinct from SecurityManager, which handles runtime security
    for the MCP server. SecurityAnalyzer focuses on static and dependency analysis
    of the test codebase itself.
    """

    def __init__(self, project_root: Union[str, Path], settings: SecuritySettings):
        """
        Initialize the SecurityAnalyzer.

        Args:
            project_root: The root directory of the project to analyze.
            settings: Security settings, potentially containing paths for tools or policies.
        """
        self.project_root = Path(project_root).resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"Project root must be a valid directory: {project_root}")
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)

        # Define common insecure patterns for test-specific checks
        self.insecure_patterns = {
            "hardcoded_secret": {
                "regex": r'(password|api_key|secret|token|auth_token|private_key)\s*=\s*["\']([^"\']+)["\']',
                "message": "Hardcoded sensitive data detected. Use environment variables or a secure vault.",
                "severity": "High",
                "suggestion": "Replace hardcoded secret with environment variable or secure configuration management.",
            },
            "os_system_usage": {
                "regex": r"os\.system\s*\(",
                "message": "Usage of os.system detected. Prefer subprocess.run with explicit arguments and input sanitization.",
                "severity": "Medium",
                "suggestion": "Replace os.system with subprocess.run(..., check=True, text=True, capture_output=True) and ensure all inputs are sanitized.",
            },
            "insecure_temp_file": {
                "regex": r"tempfile\.mktemp",
                "message": "Insecure temporary file creation detected. Use tempfile.mkstemp or TemporaryDirectory.",
                "severity": "Medium",
                "suggestion": "Use tempfile.mkstemp() or tempfile.TemporaryDirectory() for secure temporary file creation.",
            },
            "subprocess_without_check": {
                "regex": r"subprocess\.run\s*\(.*?,?\s*check\s*=\s*False",
                "message": "subprocess.run without check=True. Commands might fail silently.",
                "severity": "Low",
                "suggestion": "Ensure subprocess.run calls have check=True to raise an exception on non-zero exit codes.",
            },
            "direct_path_manipulation": {
                "regex": r'\w+\s*\+\s*["\'][/]["\']',
                "message": "Direct string concatenation for file paths. Use pathlib or os.path.join for robustness and security.",
                "severity": "Low",
                "suggestion": "Use pathlib.Path or os.path.join for constructing file paths to prevent path traversal issues.",
            },
        }

    def analyze_project_security(self) -> Dict[str, Any]:
        """
        Conducts a comprehensive security analysis of the project.

        Returns:
            A dictionary containing the full security report, including findings
            from static analysis, dependency scanning, and test-specific checks,
            along with an overall security score.
        """
        self.logger.info(
            f"Starting comprehensive security analysis for {self.project_root}"
        )
        findings: List[Dict[str, Any]] = []

        # 1. Static Code Analysis (Bandit)
        self.logger.info("Running static code analysis (Bandit)...")
        bandit_findings = self._run_static_analysis(self.project_root)
        findings.extend(bandit_findings)
        self.logger.info(f"Bandit found {len(bandit_findings)} issues.")

        # 2. Dependency Vulnerability Scanning (Safety)
        self.logger.info("Running dependency vulnerability scan (Safety)...")
        safety_findings = self._run_dependency_scan()
        findings.extend(safety_findings)
        self.logger.info(f"Safety found {len(safety_findings)} vulnerabilities.")

        # 3. Test-Specific Security Pattern Detection
        self.logger.info("Running test-specific security pattern detection...")
        test_files = list(self.project_root.rglob("test_*.py")) + list(
            self.project_root.rglob("*_test.py")
        )
        test_pattern_findings = self._analyze_test_code_for_patterns(test_files)
        findings.extend(test_pattern_findings)
        self.logger.info(
            f"Test-specific checks found {len(test_pattern_findings)} issues."
        )

        # 4. Security Policy Validation (Placeholder for more complex checks)
        self.logger.info("Validating security policies...")
        policy_findings = self._validate_security_policy()
        findings.extend(policy_findings)
        self.logger.info(f"Policy validation found {len(policy_findings)} issues.")

        # Calculate overall security score
        security_score = self.calculate_security_score(findings)
        self.logger.info(f"Overall security score: {security_score:.2f}/100")

        report = {
            "project_root": str(self.project_root),
            "analysis_date": datetime.now().isoformat(),
            "security_score": security_score,
            "total_findings": len(findings),
            "findings": findings,
            "summary": self._generate_summary(findings, security_score),
        }
        return report

    def _run_static_analysis(self, target_path: Path) -> List[Dict[str, Any]]:
        """
        Runs Bandit static analysis on the specified path.

        Args:
            target_path: The path to analyze (file or directory).

        Returns:
            A list of dictionaries, each representing a Bandit finding.
        """
        findings = []
        env = self._get_pixi_env()
        bandit_cmd = ["bandit", "-r", str(target_path), "-f", "json"]

        if not self._is_tool_available("bandit", env):
            self.logger.warning("Bandit not available. Skipping static analysis.")
            findings.append(
                {
                    "source": "PolicyViolation",
                    "type": "ToolMissing",
                    "message": "Bandit static analysis tool not found.",
                    "severity": "Low",
                    "confidence": "High",
                    "fix_suggestion": "Install Bandit (e.g., `pip install bandit` or `pixi add bandit`).",
                }
            )
            return findings

        success, output = self._run_subprocess(
            bandit_cmd, cwd=self.project_root, env=env
        )

        if success:
            try:
                bandit_report = json.loads(output)
                for result in bandit_report.get("results", []):
                    # Create a standardized finding dict for suggest_security_patch
                    finding = {
                        "source": "Bandit",
                        "severity": result.get("issue_severity"),
                        "confidence": result.get("issue_confidence"),
                        "message": result.get("issue_text"),
                        "code": result.get("code"),
                        "filename": result.get("filename"),
                        "line_number": result.get("line_number"),
                        "test_name": result.get(
                            "test_name"
                        ),  # Bandit uses test_name for B-XXX codes
                    }
                    finding["fix_suggestion"] = self.suggest_security_patch(finding)
                    findings.append(finding)
            except json.JSONDecodeError as e:
                self.logger.error(
                    f"Failed to parse Bandit output: {e}\nOutput: {output[:500]}..."
                )
                findings.append(
                    self._create_finding(
                        "BanditError",
                        f"Failed to parse Bandit output: {e}",
                        "Critical",
                        "Check Bandit installation and output format.",
                    )
                )
        else:
            self.logger.error(f"Bandit scan failed: {output}")
            findings.append(
                self._create_finding(
                    "BanditError",
                    f"Bandit scan failed: {output}",
                    "Critical",
                    "Review Bandit error logs for details.",
                )
            )
        return findings

    def _run_dependency_scan(self) -> List[Dict[str, Any]]:
        """
        Runs Safety dependency vulnerability check.

        Returns:
            A list of dictionaries, each representing a Safety finding.
        """
        findings = []
        env = self._get_pixi_env()
        safety_cmd = ["safety", "check", "--json"]

        if not self._is_tool_available("safety", env):
            self.logger.warning("Safety not available. Skipping dependency scan.")
            findings.append(
                {
                    "source": "PolicyViolation",
                    "type": "ToolMissing",
                    "message": "Safety dependency vulnerability scanner not found.",
                    "severity": "Low",
                    "confidence": "High",
                    "fix_suggestion": "Install Safety (e.g., `pip install safety` or `pixi add safety`).",
                }
            )
            return findings

        success, output = self._run_subprocess(
            safety_cmd, cwd=self.project_root, env=env
        )

        if success:
            try:
                safety_report = json.loads(output)
                for vuln in safety_report:
                    # Create a standardized finding dict for suggest_security_patch
                    finding = {
                        "source": "Safety",
                        "severity": "High",  # Safety typically reports critical/high vulnerabilities
                        "confidence": "High",
                        "message": vuln.get("advisory"),
                        "package": vuln.get("package_name"),
                        "vulnerable_version": vuln.get("vulnerable_specifier"),
                        "fixed_version": vuln.get("fix_version"),
                        "CVE": vuln.get("cve"),
                    }
                    finding["fix_suggestion"] = self.suggest_security_patch(finding)
                    findings.append(finding)
            except json.JSONDecodeError as e:
                self.logger.error(
                    f"Failed to parse Safety output: {e}\nOutput: {output[:500]}..."
                )
                findings.append(
                    self._create_finding(
                        "SafetyError",
                        f"Failed to parse Safety output: {e}",
                        "Critical",
                        "Check Safety installation and output format.",
                    )
                )
        else:
            self.logger.error(f"Safety scan failed: {output}")
            findings.append(
                self._create_finding(
                    "SafetyError",
                    f"Safety scan failed: {output}",
                    "Critical",
                    "Review Safety error logs for details.",
                )
            )
        return findings

    def _analyze_test_code_for_patterns(
        self, test_files: List[Path]
    ) -> List[Dict[str, Any]]:
        """
        Scans test files for specific insecure coding patterns.

        Args:
            test_files: A list of Path objects pointing to test files.

        Returns:
            A list of dictionaries, each representing a detected pattern.
        """
        findings = []
        for file_path in test_files:
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    for pattern_name, pattern_info in self.insecure_patterns.items():
                        match = re.search(pattern_info["regex"], line)
                        if match:
                            finding = self._create_finding(
                                pattern_name,
                                pattern_info["message"],
                                pattern_info["severity"],
                                pattern_info["suggestion"],
                                filename=str(file_path.relative_to(self.project_root)),
                                line_number=i + 1,
                                code_snippet=line.strip(),
                            )
                            findings.append(finding)
            except Exception as e:
                self.logger.error(f"Error reading or analyzing {file_path}: {e}")
        return findings

    def _validate_security_policy(self) -> List[Dict[str, Any]]:
        """
        Validates the project against defined security policies.

        Returns:
            A list of findings related to policy violations.
        """
        findings = []
        # Example policy check: Ensure authentication is required if enabled in settings
        if self.settings.require_authentication and not self.settings.auth_token:
            findings.append(
                self._create_finding(
                    "PolicyViolation",
                    "Authentication is required but no auth_token is set in settings.",
                    "Critical",
                    "Set a strong `auth_token` in SecuritySettings when `require_authentication` is True.",
                )
            )
        if (
            self.settings.enable_resource_usage_monitoring
            and self.settings.max_resource_usage_mb <= 0
        ):
            findings.append(
                self._create_finding(
                    "PolicyViolation",
                    "Resource usage monitoring is enabled but max_resource_usage_mb is not set or is zero.",
                    "Medium",
                    "Set a positive `max_resource_usage_mb` in SecuritySettings when `enable_resource_usage_monitoring` is True.",
                )
            )
        return findings

    def calculate_security_score(self, findings: List[Dict[str, Any]]) -> float:
        """
        Calculates an overall security score for the project based on findings.

        Args:
            findings: A list of security findings.

        Returns:
            The calculated security score (0-100).
        """
        score = 100.0
        severity_map = {
            "Critical": 20,
            "High": 10,
            "Medium": 5,
            "Low": 2,
        }

        for finding in findings:
            severity = finding.get("severity", "Low")
            deduction = severity_map.get(severity, 0)
            score -= deduction

        return max(0.0, score)  # Ensure score doesn't go below 0

    def generate_secure_coding_guidelines(self) -> List[str]:
        """
        Generates a list of secure coding guidelines relevant to testing.

        Returns:
            A list of strings, each representing a guideline.
        """
        guidelines = [
            "Always sanitize external inputs before using them in commands or file paths.",
            "Avoid hardcoding sensitive information (e.g., API keys, passwords) directly in code. Use environment variables or a secure vault.",
            "When executing external commands, use `subprocess.run` with `check=True` and pass arguments as a list to prevent shell injection.",
            "Use `pathlib.Path` or `os.path.join` for constructing file paths to prevent path traversal vulnerabilities.",
            "For temporary files, use `tempfile.mkstemp()` or `tempfile.TemporaryDirectory()` for secure creation and cleanup.",
            "Ensure proper access controls are in place for test data and artifacts.",
            "Regularly update dependencies and scan for known vulnerabilities.",
            "Implement robust logging for security-relevant events in tests.",
            "Avoid exposing sensitive data in test logs or error messages.",
            "Review third-party libraries and plugins for security implications before integration.",
            "Ensure test environments are isolated and cleaned up after execution.",
        ]
        return guidelines

    def suggest_security_patch(
        self, finding: Dict[str, Any]
    ) -> Optional[FixSuggestion]:
        """
        Suggests a fix for a specific security finding.

        Args:
            finding: A dictionary representing a security finding.

        Returns:
            A FixSuggestion object if a suggestion can be made, otherwise None.
        """
        source = finding.get("source")
        issue_type = finding.get("type") or finding.get(
            "test_name"
        )  # For Bandit B-XXX codes
        message = finding.get("message")

        suggestion_text = None
        explanation_text = None
        confidence = SuggestionConfidence.LOW

        if source == "Bandit":
            # Bandit findings often have a clear issue text that can be used
            suggestion_text = f"Address Bandit finding: {message}"
            explanation_text = f"Bandit detected a potential security vulnerability (ID: {issue_type}). Refer to Bandit documentation for details on {issue_type}."
            confidence = SuggestionConfidence.MEDIUM
            # Specific suggestions based on Bandit B-codes could be added here
            if issue_type == "B105":  # Hardcoded password
                suggestion_text = "Replace hardcoded password with environment variable or secure configuration."
                explanation_text = "Hardcoded passwords are a security risk. Use secure methods for credentials."
                confidence = SuggestionConfidence.HIGH
            elif issue_type == "B603":  # subprocess with shell=True
                suggestion_text = (
                    "Avoid shell=True with subprocess.run; pass arguments as a list."
                )
                explanation_text = "Using shell=True can lead to command injection. Prefer passing arguments as a list."
                confidence = SuggestionConfidence.HIGH
            elif issue_type == "B301":  # pickle
                suggestion_text = (
                    "Avoid using pickle for untrusted data; it's insecure."
                )
                explanation_text = "The pickle module is not secure against maliciously constructed data. Consider safer alternatives like JSON or protobuf for data serialization."
                confidence = SuggestionConfidence.HIGH

        elif source == "Safety":
            package = finding.get("package")
            vulnerable_version = finding.get("vulnerable_version")
            fixed_version = finding.get("fix_version")
            cve = finding.get("CVE")

            suggestion_text = (
                f"Update package '{package}' to a version >= {fixed_version}."
            )
            explanation_text = f"Dependency '{package}' (version {vulnerable_version}) has a known vulnerability (CVE: {cve or 'N/A'}). Updating to {fixed_version} or later is recommended."
            confidence = SuggestionConfidence.HIGH

        elif source == "TestPattern":
            pattern_info = self.insecure_patterns.get(issue_type)
            if pattern_info:
                suggestion_text = pattern_info["suggestion"]
                explanation_text = pattern_info["message"]
                confidence = SuggestionConfidence.from_score(
                    0.7 if pattern_info["severity"] in ["High", "Critical"] else 0.5
                )
            else:
                suggestion_text = f"Review test code for '{issue_type}' vulnerability."
                explanation_text = message
                confidence = SuggestionConfidence.MEDIUM
        elif source == "PolicyViolation":
            suggestion_text = finding.get("fix_suggestion")
            explanation_text = message
            confidence = (
                SuggestionConfidence.HIGH
                if finding.get("severity") == "Critical"
                else SuggestionConfidence.MEDIUM
            )

        if suggestion_text:
            # Generate a simple fingerprint for failure_id
            fingerprint_data = f"{source}:{issue_type}:{suggestion_text}"
            failure_id = hashlib.md5(
                fingerprint_data.encode("utf-8"), usedforsecurity=False
            ).hexdigest()[:16]

            return FixSuggestion.create(
                failure_id=failure_id,
                suggestion_text=suggestion_text,
                explanation=explanation_text or suggestion_text,
                confidence=confidence,
                code_changes=[
                    f"File: {finding.get('filename', 'N/A')}, Line: {finding.get('line_number', 'N/A')}"
                ],
                metadata={
                    "fingerprint": fingerprint_data,
                    "source": source,
                    "type": issue_type,
                },
            )
        return None

    def _create_finding(
        self,
        type: str,
        message: str,
        severity: str,
        suggestion: str,
        filename: Optional[str] = None,
        line_number: Optional[int] = None,
        code_snippet: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Helper to create a standardized finding dictionary."""
        finding = {
            "source": "TestPattern"
            if type in self.insecure_patterns
            else "PolicyViolation",
            "type": type,
            "message": message,
            "severity": severity,
            "confidence": "High",  # Default confidence for internal findings
            "filename": filename,
            "line_number": line_number,
            "code_snippet": code_snippet,
            "fix_suggestion": suggestion,
        }
        # Create the FixSuggestion separately to avoid recursion
        fix_suggestion = self.suggest_security_patch(finding)
        finding["fix_suggestion"] = fix_suggestion
        return finding

    def _generate_summary(
        self, findings: List[Dict[str, Any]], score: float
    ) -> Dict[str, Any]:
        """Generates a summary of the analysis results."""
        summary = {
            "overall_score": score,
            "total_findings": len(findings),
            "findings_by_severity": {
                "Critical": 0,
                "High": 0,
                "Medium": 0,
                "Low": 0,
                "Unknown": 0,
            },
            "findings_by_source": {},
        }

        for finding in findings:
            severity = finding.get("severity", "Unknown")
            source = finding.get("source", "Unknown")
            summary["findings_by_severity"][severity] = (
                summary["findings_by_severity"].get(severity, 0) + 1
            )
            summary["findings_by_source"][source] = (
                summary["findings_by_source"].get(source, 0) + 1
            )
        return summary

    def _run_subprocess(
        self,
        cmd: List[str],
        cwd: Optional[Path] = None,
        capture_output: bool = True,
        env: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str]:
        """Run a subprocess and return (success, output)."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.project_root,
                capture_output=capture_output,
                text=True,
                check=False,  # Do not raise CalledProcessError, we handle return code
                env=env,
            )
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stdout + "\n" + result.stderr
        except FileNotFoundError:
            return False, f"Tool not found: {cmd[0]}"
        except Exception as e:
            return False, f"Error running subprocess {cmd[0]}: {e}"

    def _get_pixi_env(self) -> Optional[Dict[str, str]]:
        """Return a copy of the current environment with pixi's .pixi/env/bin prepended to PATH, if available."""
        pixi_env_path = self.project_root / ".pixi/env/bin"
        if pixi_env_path.exists():
            env = os.environ.copy()
            env["PATH"] = str(pixi_env_path) + os.pathsep + env.get("PATH", "")
            return env
        return None

    def _is_tool_available(self, tool_name: str, env: Optional[Dict[str, str]]) -> bool:
        """Check if a tool is available in the current environment or provided env."""
        # Check current PATH
        if shutil.which(tool_name):
            return True
        # Check provided env PATH
        if env and "PATH" in env:
            for path_dir in env["PATH"].split(os.pathsep):
                if (Path(path_dir) / tool_name).exists():
                    return True
        return False
