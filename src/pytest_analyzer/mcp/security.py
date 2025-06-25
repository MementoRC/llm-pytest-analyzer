"""Security manager for MCP server.

Provides comprehensive security controls for input validation, file system access,
authentication, and rate limiting for the pytest-analyzer MCP server.
"""

import html
import os
import re
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.config_types import SecuritySettings


class SecurityError(Exception):
    """Exception raised for security violations."""

    pass


class CircuitBreakerState(Enum):
    """States for the circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class SecurityManager:
    """Main security manager for the MCP server."""

    def __init__(self, settings: SecuritySettings, project_root: Optional[str] = None):
        self.settings = settings
        self.project_root = Path(project_root or os.getcwd()).resolve()
        self._rate_limit_lock = threading.Lock()
        self._request_timestamps: Dict[str, List[float]] = {}
        self._abuse_counts: Dict[str, int] = {}
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
        self._circuit_breaker_lock = threading.Lock()

    # --- Input Validation ---

    def validate_path(self, file_path: str, read_only: bool = True) -> None:
        """Validate file path for traversal, allowlist, and permissions."""
        resolved_path = Path(file_path).resolve()
        # Path traversal prevention
        if not str(resolved_path).startswith(str(self.project_root)):
            raise SecurityError(
                f"Access denied: Path {file_path} is outside project root."
            )

        # Allowlist enforcement
        if self.settings.path_allowlist:
            allowed = any(
                str(resolved_path).startswith(str(Path(p).resolve()))
                for p in self.settings.path_allowlist
            )
            if not allowed:
                raise SecurityError(
                    f"Access denied: Path {file_path} not in allowlist."
                )

        # File type restrictions
        if self.settings.allowed_file_types:
            if resolved_path.suffix not in self.settings.allowed_file_types:
                raise SecurityError(f"File type not allowed: {resolved_path.suffix}")

        # File size restrictions
        if self.settings.max_file_size_mb is not None and resolved_path.exists():
            size_mb = resolved_path.stat().st_size / (1024 * 1024)
            if size_mb > self.settings.max_file_size_mb:
                raise SecurityError(
                    f"File too large: {size_mb:.2f} MB (max {self.settings.max_file_size_mb} MB)"
                )

        # Read/write permissions
        # Only check permissions if file exists
        if resolved_path.exists():
            if read_only and not os.access(resolved_path, os.R_OK):
                raise SecurityError(f"Read access denied: {file_path}")
            if not read_only and not os.access(resolved_path, os.W_OK):
                raise SecurityError(f"Write access denied: {file_path}")

    def sanitize_input(self, value: Any) -> Any:
        """Sanitize and escape input to prevent command injection and XSS."""
        if isinstance(value, str):
            # Remove dangerous shell metacharacters (but do not remove < or >)
            value = re.sub(r"[;&|`$]", "", value)
            # Escape HTML properly
            value = html.escape(value)
            return value
        elif isinstance(value, dict):
            return {k: self.sanitize_input(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.sanitize_input(v) for v in value]
        return value

    def prevent_command_injection(self, args: List[str]) -> List[str]:
        """Prevent command injection in argument lists."""
        safe_args = []
        for arg in args:
            if re.search(r"[;&|`$><]", arg):
                raise SecurityError(
                    f"Potential command injection detected in argument: {arg}"
                )
            safe_args.append(arg)
        return safe_args

    # --- File System Access ---

    def check_backup_and_rollback(self, file_path: str) -> None:
        """Ensure backup and rollback are enabled for write operations."""
        if not self.settings.enable_backup:
            raise SecurityError("Backup/rollback must be enabled for write operations.")
        # Backup logic is handled elsewhere; this is a policy check.

    # --- Authentication (HTTP only) ---

    def authenticate(
        self,
        token: Optional[str],
        client_cert: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        """Authenticate HTTP requests using token and/or client certificate."""
        if self.settings.require_authentication:
            if not token or token != self.settings.auth_token:
                raise SecurityError("Authentication failed: Invalid or missing token.")
        if self.settings.require_client_certificate:
            if not client_cert or client_cert not in self.settings.allowed_client_certs:
                raise SecurityError(
                    "Authentication failed: Invalid client certificate."
                )
        if self.settings.role_based_access and role is not None:
            if role not in self.settings.allowed_roles:
                raise SecurityError(f"Access denied: Role '{role}' not allowed.")

    # --- Rate Limiting ---

    def check_rate_limit(self, client_id: str, tool_name: Optional[str] = None) -> None:
        """Check and enforce rate limiting for a client, with per-tool overrides."""
        now = time.time()

        # Determine rate limit
        limit = self.settings.max_requests_per_window
        if tool_name:
            if "llm" in tool_name.lower() and self.settings.llm_rate_limit is not None:
                limit = self.settings.llm_rate_limit
            elif tool_name in self.settings.per_tool_rate_limits:
                limit = self.settings.per_tool_rate_limits[tool_name]

        with self._rate_limit_lock:
            # Use a composite key for per-tool rate limiting, but track abuse per client
            request_key = f"{client_id}:{tool_name}" if tool_name else client_id
            timestamps = self._request_timestamps.setdefault(request_key, [])

            # Remove old timestamps
            window = self.settings.rate_limit_window_seconds
            timestamps = [t for t in timestamps if now - t < window]
            self._request_timestamps[request_key] = timestamps

            # Abuse detection (per client_id)
            abuse_count = self._abuse_counts.get(client_id, 0)
            if abuse_count >= self.settings.abuse_ban_count:
                raise SecurityError(
                    f"Client '{client_id}' temporarily banned due to abuse."
                )

            if len(timestamps) >= limit:
                # Increment abuse count if over the window
                self._abuse_counts[client_id] = abuse_count + 1
                raise SecurityError(
                    f"Rate limit of {limit} req/window exceeded for key '{request_key}'."
                )

            timestamps.append(now)
            self._request_timestamps[request_key] = timestamps

            # Reset abuse count if window is empty (client is behaving)
            if not timestamps:
                self._abuse_counts[client_id] = 0

    # --- Circuit Breaker ---

    def _get_breaker(self, tool_name: str) -> Dict[str, Any]:
        """Get or create a circuit breaker for a tool."""
        with self._circuit_breaker_lock:
            if tool_name not in self._circuit_breakers:
                self._circuit_breakers[tool_name] = {
                    "state": CircuitBreakerState.CLOSED,
                    "failures": 0,
                    "successes": 0,
                    "opened_at": 0.0,
                }
            return self._circuit_breakers[tool_name]

    def check_circuit_breaker(self, tool_name: str) -> None:
        """Check the state of the circuit breaker for a tool."""
        if not self.settings.enable_circuit_breaker:
            return

        breaker = self._get_breaker(tool_name)
        state = breaker["state"]

        if state == CircuitBreakerState.OPEN:
            timeout = self.settings.circuit_breaker_timeout_seconds
            if time.time() - breaker["opened_at"] > timeout:
                breaker["state"] = CircuitBreakerState.HALF_OPEN
                breaker["successes"] = 0  # Reset successes for half-open state
            else:
                raise SecurityError(f"Circuit breaker for tool '{tool_name}' is open.")

    def record_failure(self, tool_name: str) -> None:
        """Record a failure for a tool, potentially opening the circuit."""
        if not self.settings.enable_circuit_breaker:
            return

        breaker = self._get_breaker(tool_name)

        if breaker["state"] == CircuitBreakerState.HALF_OPEN:
            # Failure in half-open state re-opens the circuit
            breaker["state"] = CircuitBreakerState.OPEN
            breaker["opened_at"] = time.time()
            breaker["failures"] = 0  # Reset failures
        elif breaker["state"] == CircuitBreakerState.CLOSED:
            breaker["failures"] += 1
            if breaker["failures"] >= self.settings.circuit_breaker_failures:
                breaker["state"] = CircuitBreakerState.OPEN
                breaker["opened_at"] = time.time()

    def record_success(self, tool_name: str) -> None:
        """Record a success for a tool, potentially closing the circuit."""
        if not self.settings.enable_circuit_breaker:
            return

        breaker = self._get_breaker(tool_name)

        if breaker["state"] == CircuitBreakerState.HALF_OPEN:
            breaker["successes"] += 1
            if breaker["successes"] >= self.settings.circuit_breaker_successes_to_close:
                # Close the circuit
                breaker["state"] = CircuitBreakerState.CLOSED
                breaker["failures"] = 0
                breaker["successes"] = 0
        elif breaker["state"] == CircuitBreakerState.CLOSED:
            # Reset failures on success in closed state to prevent flapping
            if breaker["failures"] > 0:
                breaker["failures"] = 0

    def monitor_resource_usage(self, usage_mb: float) -> None:
        """Monitor resource usage and enforce limits."""
        if usage_mb > self.settings.max_resource_usage_mb:
            raise SecurityError(
                f"Resource usage exceeded: {usage_mb} MB (max {self.settings.max_resource_usage_mb} MB)"
            )

    # --- Utility ---

    def validate_tool_input(
        self, tool_name: str, arguments: Dict[str, Any], read_only: bool = True
    ) -> Dict[str, Any]:
        """Run all relevant security checks for a tool invocation."""
        # Prevent command injection in argument lists BEFORE sanitization
        if "pytest_args" in arguments and isinstance(arguments["pytest_args"], list):
            self.prevent_command_injection(arguments["pytest_args"])
        # Sanitize all string inputs
        sanitized_args = self.sanitize_input(arguments)
        # Path validation for any file path arguments
        for key, value in sanitized_args.items():
            if "path" in key or "file" in key:
                if isinstance(value, str):
                    self.validate_path(value, read_only=read_only)
                elif isinstance(value, list):
                    for v in value:
                        if isinstance(v, str):
                            self.validate_path(v, read_only=read_only)
        # File size/type checks are handled in validate_path
        return sanitized_args

    def get_project_root(self) -> str:
        return str(self.project_root)
