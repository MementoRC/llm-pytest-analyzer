"""Tests for the git_manager module."""

import subprocess
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

from pytest_analyzer.utils.git_manager import (
    GitError,
    check_git_installed,
    commit_fix,
    confirm_git_setup,
    create_branch_for_fixes,
    create_gitignore,
    get_git_root,
    init_git_repository,
    is_git_repository,
    is_working_tree_clean,
    reset_file,
)


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run to prevent actual command execution."""
    with patch("subprocess.run") as mock_run:
        # Default successful response
        mock_process = MagicMock()
        mock_process.stdout = "success"
        mock_process.stderr = ""
        mock_run.return_value = mock_process
        yield mock_run


@pytest.fixture
def mock_project_dir(tmp_path):
    """Create a temporary project directory for testing."""
    return tmp_path


def test_check_git_installed_success(mock_subprocess):
    """Test check_git_installed when git is successfully found."""
    mock_subprocess.return_value.stdout = "git version 2.30.0"

    result = check_git_installed()

    assert result is True
    mock_subprocess.assert_called_once_with(
        ["git", "--version"], capture_output=True, check=True, text=True
    )


def test_check_git_installed_failure(mock_subprocess):
    """Test check_git_installed when git command fails."""
    mock_subprocess.side_effect = FileNotFoundError("No such file or directory: git")

    result = check_git_installed()

    assert result is False
    mock_subprocess.assert_called_once()


def test_check_git_installed_error(mock_subprocess):
    """Test check_git_installed when git command returns an error."""
    mock_subprocess.side_effect = subprocess.CalledProcessError(1, "git")

    result = check_git_installed()

    assert result is False
    mock_subprocess.assert_called_once()


def test_is_git_repository_true_file_path(mock_subprocess, mock_project_dir):
    """Test is_git_repository with a file path in a git repo."""
    # Create a test file
    test_file = mock_project_dir / "test_file.txt"
    test_file.touch()

    mock_subprocess.return_value.stdout = "true"

    result = is_git_repository(str(test_file))

    assert result is True
    mock_subprocess.assert_called_once_with(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=mock_project_dir,
        capture_output=True,
        check=True,
        text=True,
    )


def test_is_git_repository_true_dir_path(mock_subprocess, mock_project_dir):
    """Test is_git_repository with a directory path that is a git repo."""
    mock_subprocess.return_value.stdout = "true"

    result = is_git_repository(str(mock_project_dir))

    assert result is True
    mock_subprocess.assert_called_once_with(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=mock_project_dir,
        capture_output=True,
        check=True,
        text=True,
    )


def test_is_git_repository_false(mock_subprocess, mock_project_dir):
    """Test is_git_repository when the path is not in a git repo."""
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        128, ["git", "rev-parse", "--is-inside-work-tree"]
    )

    result = is_git_repository(str(mock_project_dir))

    assert result is False
    mock_subprocess.assert_called_once()


def test_create_gitignore_new_file(mock_project_dir):
    """Test create_gitignore when .gitignore doesn't exist."""
    with patch("builtins.open", mock_open()) as mock_file:
        create_gitignore(mock_project_dir)

        # Check that open was called with the right file path
        mock_file.assert_called_once_with(mock_project_dir / ".gitignore", "w")

        # Check that the basic ignores were written
        handle = mock_file()
        written_content = handle.write.call_args[0][0]

        assert "__pycache__/" in written_content
        assert "*.py[cod]" in written_content
        assert ".pytest_cache/" in written_content
        assert "*.pytest-analyzer.bak" in written_content


def test_create_gitignore_existing_file(mock_project_dir):
    """Test create_gitignore when .gitignore already exists."""
    # Create a .gitignore file
    gitignore_path = mock_project_dir / ".gitignore"
    gitignore_path.touch()

    with patch("pathlib.Path.exists", return_value=True):
        create_gitignore(mock_project_dir)

        # The file should still exist but no writes should have occurred
        assert gitignore_path.exists()


def test_create_gitignore_io_error(mock_project_dir):
    """Test create_gitignore when there's an IO error."""
    with patch("builtins.open", side_effect=IOError("Permission denied")):
        # This should not raise an exception
        create_gitignore(mock_project_dir)


def test_init_git_repository_success(mock_subprocess, mock_project_dir):
    """Test init_git_repository with a successful initialization."""
    result = init_git_repository(str(mock_project_dir))

    assert result is True
    # Check that git init, add, and commit were called
    assert mock_subprocess.call_count == 3
    expected_calls = [
        call(
            ["git", "init"],
            cwd=mock_project_dir,
            capture_output=True,
            check=True,
            text=True,
        ),
        call(
            ["git", "add", "."],
            cwd=mock_project_dir,
            capture_output=True,
            check=True,
            text=True,
        ),
        call(
            ["git", "commit", "-m", "Initial commit by pytest-analyzer"],
            cwd=mock_project_dir,
            capture_output=True,
            check=True,
            text=True,
        ),
    ]
    mock_subprocess.assert_has_calls(expected_calls)


def test_init_git_repository_file_path(mock_subprocess, mock_project_dir):
    """Test init_git_repository with a file path instead of directory."""
    # Create a test file
    test_file = mock_project_dir / "test_file.txt"
    test_file.touch()

    result = init_git_repository(str(test_file))

    assert result is True
    # Git commands should be called with the parent directory
    expected_calls = [
        call(
            ["git", "init"],
            cwd=mock_project_dir,
            capture_output=True,
            check=True,
            text=True,
        ),
        call(
            ["git", "add", "."],
            cwd=mock_project_dir,
            capture_output=True,
            check=True,
            text=True,
        ),
        call(
            ["git", "commit", "-m", "Initial commit by pytest-analyzer"],
            cwd=mock_project_dir,
            capture_output=True,
            check=True,
            text=True,
        ),
    ]
    mock_subprocess.assert_has_calls(expected_calls)


def test_init_git_repository_error(mock_subprocess, mock_project_dir):
    """Test init_git_repository when an error occurs."""
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        1, ["git", "init"], stderr="fatal: could not initialize repository"
    )

    result = init_git_repository(str(mock_project_dir))

    assert result is False
    mock_subprocess.assert_called_once()


@patch("pytest_analyzer.utils.git_manager.check_git_installed")
@patch("pytest_analyzer.utils.git_manager.is_git_repository")
@patch("pytest_analyzer.utils.git_manager.init_git_repository")
def test_confirm_git_setup_git_not_installed(mock_init, mock_is_repo, mock_check):
    """Test confirm_git_setup when git is not installed."""
    mock_check.return_value = False

    with patch("builtins.print") as mock_print:
        result = confirm_git_setup("/project")

        assert result is False
        mock_print.assert_called_once_with(
            "Git is not installed or not in PATH. Fix suggestions will be generated but cannot be applied automatically."
        )
        mock_check.assert_called_once()
        mock_is_repo.assert_not_called()
        mock_init.assert_not_called()


@patch("pytest_analyzer.utils.git_manager.check_git_installed")
@patch("pytest_analyzer.utils.git_manager.is_git_repository")
@patch("pytest_analyzer.utils.git_manager.init_git_repository")
def test_confirm_git_setup_already_git_repo(mock_init, mock_is_repo, mock_check):
    """Test confirm_git_setup when project is already a git repo."""
    mock_check.return_value = True
    mock_is_repo.return_value = True

    result = confirm_git_setup("/project")

    assert result is True
    mock_check.assert_called_once()
    mock_is_repo.assert_called_once_with("/project")
    mock_init.assert_not_called()


@patch("pytest_analyzer.utils.git_manager.check_git_installed")
@patch("pytest_analyzer.utils.git_manager.is_git_repository")
@patch("pytest_analyzer.utils.git_manager.init_git_repository")
def test_confirm_git_setup_init_success(mock_init, mock_is_repo, mock_check):
    """Test confirm_git_setup with successful initialization."""
    mock_check.return_value = True
    mock_is_repo.return_value = False
    mock_init.return_value = True

    with patch("builtins.input", return_value="y"):
        with patch("builtins.print") as mock_print:
            result = confirm_git_setup("/project")

            assert result is True
            mock_check.assert_called_once()
            mock_is_repo.assert_called_once_with("/project")
            mock_init.assert_called_once_with("/project")
            mock_print.assert_called_with(
                "Git repository initialized with an initial commit."
            )


@patch("pytest_analyzer.utils.git_manager.check_git_installed")
@patch("pytest_analyzer.utils.git_manager.is_git_repository")
@patch("pytest_analyzer.utils.git_manager.init_git_repository")
def test_confirm_git_setup_init_failure(mock_init, mock_is_repo, mock_check):
    """Test confirm_git_setup when initialization fails."""
    mock_check.return_value = True
    mock_is_repo.return_value = False
    mock_init.return_value = False

    with patch("builtins.input", return_value="y"):
        with patch("builtins.print") as mock_print:
            result = confirm_git_setup("/project")

            assert result is False
            mock_check.assert_called_once()
            mock_is_repo.assert_called_once_with("/project")
            mock_init.assert_called_once_with("/project")
            mock_print.assert_called_with(
                "Failed to initialize Git repository. Fix suggestions will be generated but cannot be applied automatically."
            )


@patch("pytest_analyzer.utils.git_manager.check_git_installed")
@patch("pytest_analyzer.utils.git_manager.is_git_repository")
@patch("pytest_analyzer.utils.git_manager.init_git_repository")
def test_confirm_git_setup_user_declines(mock_init, mock_is_repo, mock_check):
    """Test confirm_git_setup when user declines initialization."""
    mock_check.return_value = True
    mock_is_repo.return_value = False

    with patch("builtins.input", return_value="n"):
        with patch("builtins.print") as mock_print:
            result = confirm_git_setup("/project")

            assert result is False
            mock_check.assert_called_once()
            mock_is_repo.assert_called_once_with("/project")
            mock_init.assert_not_called()
            mock_print.assert_called_with(
                "Proceeding without Git integration. Fix suggestions will be generated but cannot be applied automatically."
            )


def test_get_git_root_success(mock_subprocess, mock_project_dir):
    """Test get_git_root with a valid git repository."""
    mock_subprocess.return_value.stdout = str(mock_project_dir)

    result = get_git_root(str(mock_project_dir))

    assert result == str(mock_project_dir)
    mock_subprocess.assert_called_once_with(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=mock_project_dir,
        capture_output=True,
        check=True,
        text=True,
    )


def test_get_git_root_file_path(mock_subprocess, mock_project_dir):
    """Test get_git_root with a file path."""
    # Create a test file
    test_file = mock_project_dir / "test_file.txt"
    test_file.touch()

    mock_subprocess.return_value.stdout = str(mock_project_dir)

    result = get_git_root(str(test_file))

    assert result == str(mock_project_dir)
    mock_subprocess.assert_called_once_with(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=mock_project_dir,
        capture_output=True,
        check=True,
        text=True,
    )


def test_get_git_root_error(mock_subprocess, mock_project_dir):
    """Test get_git_root when an error occurs."""
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        128, ["git", "rev-parse", "--show-toplevel"]
    )

    result = get_git_root(str(mock_project_dir))

    assert result is None
    mock_subprocess.assert_called_once()


def test_create_branch_for_fixes_success(mock_subprocess, mock_project_dir):
    """Test create_branch_for_fixes with successful branch creation."""
    # Mock the current branch name
    mock_subprocess.return_value.stdout = "main"

    result = create_branch_for_fixes(str(mock_project_dir), "fix-branch")

    assert result == ("fix-branch", "main")
    mock_subprocess.assert_has_calls(
        [
            call(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(mock_project_dir),
                capture_output=True,
                check=True,
                text=True,
            ),
            call(
                ["git", "checkout", "-b", "fix-branch"],
                cwd=str(mock_project_dir),
                capture_output=True,
                check=True,
                text=True,
            ),
        ]
    )


def test_create_branch_for_fixes_auto_name(mock_subprocess, mock_project_dir):
    """Test create_branch_for_fixes with auto-generated branch name."""
    # Mock the current branch name
    mock_subprocess.return_value.stdout = "main"

    with patch("time.time", return_value=12345):
        result = create_branch_for_fixes(str(mock_project_dir))

        assert result[0] == "pytest-analyzer-fixes-12345"
        assert result[1] == "main"
        mock_subprocess.assert_has_calls(
            [
                call(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(mock_project_dir),
                    capture_output=True,
                    check=True,
                    text=True,
                ),
                call(
                    ["git", "checkout", "-b", "pytest-analyzer-fixes-12345"],
                    cwd=str(mock_project_dir),
                    capture_output=True,
                    check=True,
                    text=True,
                ),
            ]
        )


def test_create_branch_for_fixes_error(mock_subprocess, mock_project_dir):
    """Test create_branch_for_fixes when an error occurs."""
    # First call succeeds (get current branch)
    # Second call fails (create branch)
    success_result = MagicMock()
    success_result.stdout = "main"

    mock_subprocess.side_effect = [
        success_result,
        subprocess.CalledProcessError(
            1,
            ["git", "checkout", "-b"],
            stderr="fatal: A branch named 'fix-branch' already exists.",
        ),
    ]

    with pytest.raises(GitError):
        create_branch_for_fixes(str(mock_project_dir), "fix-branch")

    mock_subprocess.assert_has_calls(
        [
            call(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(mock_project_dir),
                capture_output=True,
                check=True,
                text=True,
            ),
            call(
                ["git", "checkout", "-b", "fix-branch"],
                cwd=str(mock_project_dir),
                capture_output=True,
                check=True,
                text=True,
            ),
        ]
    )


def test_is_working_tree_clean_true(mock_subprocess, mock_project_dir):
    """Test is_working_tree_clean when working tree is clean."""
    mock_subprocess.return_value.stdout = ""

    result = is_working_tree_clean(str(mock_project_dir))

    assert result is True
    mock_subprocess.assert_called_once_with(
        ["git", "status", "--porcelain"],
        cwd=str(mock_project_dir),
        capture_output=True,
        check=True,
        text=True,
    )


def test_is_working_tree_clean_false(mock_subprocess, mock_project_dir):
    """Test is_working_tree_clean when working tree has changes."""
    mock_subprocess.return_value.stdout = " M modified_file.txt\n?? untracked_file.txt"

    result = is_working_tree_clean(str(mock_project_dir))

    assert result is False
    mock_subprocess.assert_called_once()


def test_is_working_tree_clean_error(mock_subprocess, mock_project_dir):
    """Test is_working_tree_clean when an error occurs."""
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        1, ["git", "status", "--porcelain"]
    )

    result = is_working_tree_clean(str(mock_project_dir))

    assert result is False
    mock_subprocess.assert_called_once()


def test_commit_fix_success(mock_subprocess, mock_project_dir):
    """Test commit_fix with successful commit."""
    # Create a test file
    test_file = mock_project_dir / "test_file.txt"
    test_file.touch()

    with patch("pathlib.Path.exists", return_value=True):
        result = commit_fix(str(mock_project_dir), str(test_file), "Test issue")

        assert result is True
        mock_subprocess.assert_has_calls(
            [
                call(
                    ["git", "add", str(test_file.resolve())],
                    cwd=str(mock_project_dir),
                    capture_output=True,
                    check=True,
                    text=True,
                ),
                call(
                    [
                        "git",
                        "commit",
                        "-m",
                        f"fix: Apply pytest-analyzer fix for Test issue in {test_file.name}",
                    ],
                    cwd=str(mock_project_dir),
                    capture_output=True,
                    check=True,
                    text=True,
                ),
            ]
        )


def test_commit_fix_file_not_exists(mock_subprocess, mock_project_dir):
    """Test commit_fix when file doesn't exist."""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(GitError):
            commit_fix(str(mock_project_dir), "/nonexistent/file.txt", "Test issue")

        mock_subprocess.assert_not_called()


def test_commit_fix_add_error(mock_subprocess, mock_project_dir):
    """Test commit_fix when git add fails."""
    # Create a test file
    test_file = mock_project_dir / "test_file.txt"
    test_file.touch()

    mock_subprocess.side_effect = subprocess.CalledProcessError(
        1,
        ["git", "add"],
        stderr="fatal: pathspec 'test_file.txt' did not match any files",
    )

    with patch("pathlib.Path.exists", return_value=True):
        result = commit_fix(str(mock_project_dir), str(test_file), "Test issue")

        assert result is False
        mock_subprocess.assert_called_once()


def test_commit_fix_commit_error(mock_subprocess, mock_project_dir):
    """Test commit_fix when git commit fails."""
    # Create a test file
    test_file = mock_project_dir / "test_file.txt"
    test_file.touch()

    # First call succeeds (git add)
    # Second call fails (git commit)
    success_result = MagicMock()

    mock_subprocess.side_effect = [
        success_result,
        subprocess.CalledProcessError(
            1, ["git", "commit"], stderr="fatal: unable to auto-detect email address"
        ),
    ]

    with patch("pathlib.Path.exists", return_value=True):
        result = commit_fix(str(mock_project_dir), str(test_file), "Test issue")

        assert result is False
        assert mock_subprocess.call_count == 2


def test_reset_file_success(mock_subprocess, mock_project_dir):
    """Test reset_file with successful reset."""
    # Create a test file
    test_file = mock_project_dir / "test_file.txt"
    test_file.touch()

    result = reset_file(str(mock_project_dir), str(test_file))

    assert result is True
    mock_subprocess.assert_called_once_with(
        ["git", "checkout", "HEAD", "--", str(test_file.resolve())],
        cwd=str(mock_project_dir),
        capture_output=True,
        check=True,
        text=True,
    )


def test_reset_file_error(mock_subprocess, mock_project_dir):
    """Test reset_file when an error occurs."""
    # Create a test file
    test_file = mock_project_dir / "test_file.txt"
    test_file.touch()

    mock_subprocess.side_effect = subprocess.CalledProcessError(
        1,
        ["git", "checkout"],
        stderr="error: pathspec 'test_file.txt' did not match any file(s) known to git",
    )

    result = reset_file(str(mock_project_dir), str(test_file))

    assert result is False
    mock_subprocess.assert_called_once()
