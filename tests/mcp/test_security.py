"""Comprehensive tests for SecurityManager and SecuritySettings."""

import os
import threading
import time

import pytest

from src.pytest_analyzer.mcp.security import (
    SecurityError,
    SecurityManager,
)
from src.pytest_analyzer.utils.config_types import SecuritySettings

# --- Fixtures ---


@pytest.fixture
def tmp_project_root(tmp_path):
    # Create a fake project root with some files
    root = tmp_path / "project"
    root.mkdir()
    (root / "allowed.txt").write_text("hello")
    (root / "allowed.py").write_text("print('hi')")
    (root / "large.txt").write_bytes(b"x" * 1024 * 1024 * 5)  # 5MB
    (root / "forbidden.xml").write_text("<xml></xml>")
    (root / "subdir").mkdir()
    (root / "subdir" / "nested.py").write_text("pass")
    return root


@pytest.fixture
def default_settings(tmp_project_root):
    return SecuritySettings(
        path_allowlist=[str(tmp_project_root)],
        allowed_file_types=[".py", ".txt"],
        max_file_size_mb=4.0,
        enable_input_sanitization=True,
        restrict_to_project_dir=True,
        enable_backup=True,
        require_authentication=True,
        auth_token="secret",
        require_client_certificate=True,
        allowed_client_certs=["cert1", "cert2"],
        role_based_access=True,
        allowed_roles={"admin", "user"},
        max_requests_per_window=3,
        rate_limit_window_seconds=2,
        abuse_threshold=4,
        abuse_ban_count=1,
        max_resource_usage_mb=10.0,
        enable_resource_usage_monitoring=True,
    )


@pytest.fixture
def security_manager(default_settings, tmp_project_root):
    return SecurityManager(default_settings, project_root=str(tmp_project_root))


# --- SecuritySettings validation ---


def test_security_settings_validation_success(tmp_path):
    s = SecuritySettings(
        path_allowlist=[str(tmp_path)],
        allowed_file_types=[".py", ".txt"],
        max_file_size_mb=1.0,
        max_requests_per_window=1,
        rate_limit_window_seconds=1,
        abuse_threshold=1,
        abuse_ban_count=1,
        max_resource_usage_mb=1.0,
    )
    assert s.max_file_size_mb == 1.0
    assert s.allowed_file_types == [".py", ".txt"]


def test_security_settings_validation_errors():
    with pytest.raises(ValueError):
        SecuritySettings(max_file_size_mb=0)
    with pytest.raises(ValueError):
        SecuritySettings(max_requests_per_window=0)
    with pytest.raises(ValueError):
        SecuritySettings(rate_limit_window_seconds=0)
    with pytest.raises(ValueError):
        SecuritySettings(max_resource_usage_mb=0)
    with pytest.raises(ValueError):
        SecuritySettings(abuse_threshold=-1)
    with pytest.raises(ValueError):
        SecuritySettings(allowed_file_types=["py", "txt"])  # missing dot


# --- Path validation ---


def test_validate_path_allows_allowed_file(security_manager, tmp_project_root):
    allowed = tmp_project_root / "allowed.txt"
    security_manager.validate_path(str(allowed))


def test_validate_path_denies_outside_project(security_manager, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("bad")
    with pytest.raises(SecurityError, match="outside project root"):
        security_manager.validate_path(str(outside))


def test_validate_path_enforces_allowlist(security_manager, tmp_path):
    # Remove allowlist, should deny
    sm = SecurityManager(
        SecuritySettings(
            path_allowlist=[str(tmp_path / "other")],
            allowed_file_types=[".txt"],
        ),
        project_root=tmp_path,
    )
    f = tmp_path / "foo.txt"
    f.write_text("x")
    with pytest.raises(SecurityError, match="not in allowlist"):
        sm.validate_path(str(f))


def test_validate_path_file_type(security_manager, tmp_project_root):
    forbidden = tmp_project_root / "forbidden.xml"
    with pytest.raises(SecurityError, match="File type not allowed"):
        security_manager.validate_path(str(forbidden))


def test_validate_path_file_size(security_manager, tmp_project_root):
    large = tmp_project_root / "large.txt"
    with pytest.raises(SecurityError, match="File too large"):
        security_manager.validate_path(str(large))


def test_validate_path_permissions(security_manager, tmp_project_root):
    file = tmp_project_root / "allowed.txt"
    # Remove read permission
    file.chmod(0o000)
    try:
        with pytest.raises(SecurityError, match="Read access denied"):
            security_manager.validate_path(str(file))
    finally:
        file.chmod(0o644)


def test_validate_path_write_permissions(security_manager, tmp_project_root):
    file = tmp_project_root / "allowed.txt"
    # Remove write permission
    file.chmod(0o444)
    try:
        with pytest.raises(SecurityError, match="Write access denied"):
            security_manager.validate_path(str(file), read_only=False)
    finally:
        file.chmod(0o644)


# --- Input sanitization ---


def test_sanitize_input_strips_shell_chars(security_manager):
    s = "rm -rf /; echo $HOME | cat"
    sanitized = security_manager.sanitize_input(s)
    assert ";" not in sanitized and "|" not in sanitized and "$" not in sanitized


def test_sanitize_input_escapes_html(security_manager):
    s = "<script>alert(1)</script>"
    sanitized = security_manager.sanitize_input(s)
    assert "<" not in sanitized and ">" not in sanitized
    assert "&lt;" in sanitized and "&gt;" in sanitized


def test_sanitize_input_dict_and_list(security_manager):
    d = {"a": "<b>", "b": ["foo&bar", "<baz>"]}
    sanitized = security_manager.sanitize_input(d)
    assert sanitized["a"] == "&lt;b&gt;"
    assert sanitized["b"][1] == "&lt;baz&gt;"


def test_prevent_command_injection_allows_safe(security_manager):
    args = ["pytest", "-v", "test_file.py"]
    assert security_manager.prevent_command_injection(args) == args


def test_prevent_command_injection_blocks_unsafe(security_manager):
    args = ["pytest", ";rm -rf /"]
    with pytest.raises(SecurityError, match="Potential command injection"):
        security_manager.prevent_command_injection(args)


# --- Authentication ---


def test_authenticate_success(security_manager):
    security_manager.authenticate(token="secret", client_cert="cert1", role="admin")


def test_authenticate_invalid_token(security_manager):
    with pytest.raises(SecurityError, match="Invalid or missing token"):
        security_manager.authenticate(token="wrong", client_cert="cert1", role="admin")


def test_authenticate_invalid_cert(security_manager):
    with pytest.raises(SecurityError, match="Invalid client certificate"):
        security_manager.authenticate(token="secret", client_cert="bad", role="admin")


def test_authenticate_invalid_role(security_manager):
    with pytest.raises(SecurityError, match="not allowed"):
        security_manager.authenticate(
            token="secret", client_cert="cert1", role="readonly"
        )


def test_authenticate_missing_token(security_manager):
    with pytest.raises(SecurityError, match="Invalid or missing token"):
        security_manager.authenticate(token=None, client_cert="cert1", role="admin")


def test_authenticate_missing_cert(security_manager):
    with pytest.raises(SecurityError, match="Invalid client certificate"):
        security_manager.authenticate(token="secret", client_cert=None, role="admin")


def test_authenticate_missing_role(security_manager):
    # Should fail if role is not in allowed_roles
    with pytest.raises(SecurityError, match="not allowed"):
        security_manager.authenticate(
            token="secret", client_cert="cert1", role="readonly"
        )


def test_authenticate_role_not_required(security_manager):
    # If role_based_access is False, role is ignored
    sm = SecurityManager(
        SecuritySettings(
            require_authentication=True,
            auth_token="secret",
            require_client_certificate=True,
            allowed_client_certs=["cert1"],
            role_based_access=False,
        ),
        project_root=os.getcwd(),
    )
    sm.authenticate(
        token="secret", client_cert="cert1", role="readonly"
    )  # Should not raise


# --- Rate limiting ---


def test_rate_limit_allows_within_limit(security_manager):
    for _ in range(3):
        security_manager.check_rate_limit("client1")


def test_rate_limit_blocks_over_limit(security_manager):
    for _ in range(3):
        security_manager.check_rate_limit("client2")
    with pytest.raises(SecurityError, match="Rate limit exceeded"):
        security_manager.check_rate_limit("client2")


def test_rate_limit_window_expiry(security_manager):
    for _ in range(3):
        security_manager.check_rate_limit("client3")
    time.sleep(security_manager.settings.rate_limit_window_seconds + 0.1)
    # Should allow again after window
    security_manager.check_rate_limit("client3")


def test_rate_limit_multiple_clients(security_manager):
    for _ in range(3):
        security_manager.check_rate_limit("clientA")
        security_manager.check_rate_limit("clientB")
    with pytest.raises(SecurityError):
        security_manager.check_rate_limit("clientA")
    with pytest.raises(SecurityError):
        security_manager.check_rate_limit("clientB")


def test_rate_limit_abuse_detection(security_manager):
    # abuse_threshold=4, abuse_ban_count=1
    for _ in range(5):
        try:
            security_manager.check_rate_limit("abuser")
        except SecurityError:
            pass
    # Should be banned after exceeding abuse_ban_count
    with pytest.raises(SecurityError, match="temporarily banned"):
        security_manager.check_rate_limit("abuser")


# --- Resource usage monitoring ---


def test_monitor_resource_usage_allows(security_manager):
    security_manager.monitor_resource_usage(5.0)


def test_monitor_resource_usage_blocks(security_manager):
    with pytest.raises(SecurityError, match="Resource usage exceeded"):
        security_manager.monitor_resource_usage(20.0)


# --- Tool input validation ---


def test_validate_tool_input_sanitizes_and_validates(
    security_manager, tmp_project_root
):
    args = {
        "file_path": str(tmp_project_root / "allowed.txt"),
        "pytest_args": ["-v", "test.py"],
        "other": "<b>",
    }
    sanitized = security_manager.validate_tool_input("pytest", args)
    assert sanitized["other"] == "&lt;b&gt;"


def test_validate_tool_input_blocks_bad_path(security_manager, tmp_path):
    args = {"file_path": str(tmp_path / "not_allowed.txt")}
    with pytest.raises(SecurityError):
        security_manager.validate_tool_input("pytest", args)


def test_validate_tool_input_blocks_command_injection(
    security_manager, tmp_project_root
):
    args = {
        "file_path": str(tmp_project_root / "allowed.txt"),
        "pytest_args": ["-v", ";rm -rf /"],
    }
    with pytest.raises(SecurityError):
        security_manager.validate_tool_input("pytest", args)


# --- Thread safety ---


def test_rate_limit_thread_safety(security_manager):
    # Simulate many threads hitting rate limit
    errors = []

    def worker():
        try:
            for _ in range(2):
                security_manager.check_rate_limit("threaded")
        except SecurityError:
            errors.append(1)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # At least some threads should hit the rate limit
    assert errors


# --- Utility ---


def test_get_project_root_returns_str(security_manager, tmp_project_root):
    assert security_manager.get_project_root() == str(tmp_project_root)
