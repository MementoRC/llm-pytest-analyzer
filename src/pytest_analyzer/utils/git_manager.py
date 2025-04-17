"""
Git integration for pytest-analyzer.

This module provides utilities to check Git compatibility, initialize Git repositories,
and manage code changes through Git operations rather than custom backup methods.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

class GitError(Exception):
    """Exception raised for Git-related errors."""
    pass

def check_git_installed() -> bool:
    """
    Check if Git is installed and accessible in the system PATH.
    
    :return: True if Git is installed, False otherwise
    """
    try:
        subprocess.run(['git', '--version'], 
                      capture_output=True, 
                      check=True, 
                      text=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.warning("Git is not installed or not found in the PATH")
        return False

def is_git_repository(path: str) -> bool:
    """
    Check if the specified path is inside a Git repository.
    
    :param path: Path to check
    :return: True if the path is inside a Git repository, False otherwise
    """
    try:
        # Use the directory containing the path if it's a file
        project_dir = Path(path)
        if project_dir.is_file():
            project_dir = project_dir.parent
            
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=project_dir,
            capture_output=True,
            check=True,
            text=True
        )
        return result.stdout.strip() == 'true'
    except subprocess.CalledProcessError:
        return False

def create_gitignore(project_path: Path) -> None:
    """
    Create a basic .gitignore file if one doesn't exist.
    
    :param project_path: Path to the project directory
    """
    gitignore_path = project_path / ".gitignore"
    
    if not gitignore_path.exists():
        basic_ignores = [
            "# Pytest cache",
            "__pycache__/",
            "*.py[cod]",
            "*$py.class",
            ".pytest_cache/",
            ".coverage",
            "htmlcov/",
            ".tox/",
            "*.egg-info/",
            "venv/",
            "env/",
            ".env",
            ".venv",
            "dist/",
            "build/",
            "# Editor files",
            ".idea/",
            ".vscode/",
            "*.swp",
            "*.swo",
            "*~",
            "# pytest-analyzer specific",
            "*.pytest-analyzer.bak",
        ]
        
        try:
            with open(gitignore_path, "w") as f:
                f.write("\n".join(basic_ignores))
            logger.info(f"Created .gitignore at {gitignore_path}")
        except IOError as e:
            logger.warning(f"Failed to create .gitignore: {e}")

def init_git_repository(project_path: str, force: bool = False) -> bool:
    """
    Initialize a Git repository and create an initial commit.
    
    :param project_path: Path to the project directory
    :param force: If True, initialize without user confirmation
    :return: True if initialization succeeded, False otherwise
    """
    project_dir = Path(project_path)
    if project_dir.is_file():
        project_dir = project_dir.parent
    
    try:
        # Initialize Git
        subprocess.run(
            ['git', 'init'],
            cwd=project_dir,
            capture_output=True,
            check=True,
            text=True
        )
        logger.info(f"Initialized Git repository at {project_dir}")
        
        # Create .gitignore
        create_gitignore(project_dir)
        
        # Stage all files
        subprocess.run(
            ['git', 'add', '.'],
            cwd=project_dir,
            capture_output=True,
            check=True,
            text=True
        )
        
        # Initial commit
        subprocess.run(
            ['git', 'commit', '-m', 'Initial commit by pytest-analyzer'],
            cwd=project_dir,
            capture_output=True,
            check=True,
            text=True
        )
        
        logger.info("Created initial commit")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error initializing Git repository: {e.stderr}")
        return False

def confirm_git_setup(project_path: str) -> bool:
    """
    Check Git compatibility and set up if needed and confirmed by user.
    
    :param project_path: Path to the project directory
    :return: True if Git is available and ready to use, False otherwise
    """
    # Check if Git is installed
    if not check_git_installed():
        print("Git is not installed or not in PATH. Fix suggestions will be generated but cannot be applied automatically.")
        return False
    
    # Check if the project is already a Git repository
    if is_git_repository(project_path):
        logger.info(f"Project at {project_path} is already a Git repository")
        return True
    
    # Ask user confirmation to initialize Git
    print(f"The project at {project_path} is not under Git version control.")
    response = input("Would you like to initialize a Git repository to track changes? (y/n): ")
    
    if response.lower() == 'y':
        if init_git_repository(project_path):
            print("Git repository initialized with an initial commit.")
            return True
        else:
            print("Failed to initialize Git repository. Fix suggestions will be generated but cannot be applied automatically.")
            return False
    else:
        print("Proceeding without Git integration. Fix suggestions will be generated but cannot be applied automatically.")
        return False

def get_git_root(path: str) -> Optional[str]:
    """
    Get the root directory of the Git repository containing the specified path.
    
    :param path: Path within a Git repository
    :return: Path to the Git root directory or None if not a Git repository
    """
    try:
        project_dir = Path(path)
        if project_dir.is_file():
            project_dir = project_dir.parent
            
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            cwd=project_dir,
            capture_output=True,
            check=True,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def create_branch_for_fixes(repo_path: str, branch_name: Optional[str] = None) -> Tuple[str, str]:
    """
    Create and checkout a new branch for applying fixes.
    
    :param repo_path: Path to the Git repository
    :param branch_name: Optional custom branch name. If None, a name will be generated.
    :return: Tuple of (new branch name, original branch name)
    """
    try:
        # Get current branch name
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_path,
            capture_output=True,
            check=True,
            text=True
        )
        original_branch = result.stdout.strip()
        
        # Generate branch name if not provided
        if not branch_name:
            import time
            timestamp = int(time.time())
            branch_name = f"pytest-analyzer-fixes-{timestamp}"
        
        # Create and checkout the new branch
        subprocess.run(
            ['git', 'checkout', '-b', branch_name],
            cwd=repo_path,
            capture_output=True,
            check=True,
            text=True
        )
        logger.info(f"Created and switched to branch: {branch_name}")
        return branch_name, original_branch
    except subprocess.CalledProcessError as e:
        logger.error(f"Error creating Git branch: {e.stderr}")
        raise GitError(f"Failed to create branch {branch_name}: {e.stderr}")

def is_working_tree_clean(repo_path: str) -> bool:
    """
    Check if the Git working directory has uncommitted changes.
    
    :param repo_path: Path to the Git repository
    :return: True if working tree is clean, False otherwise
    """
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=repo_path,
            capture_output=True,
            check=True,
            text=True
        )
        return not bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False

def commit_fix(repo_path: str, file_path: str, issue_description: str) -> bool:
    """
    Commit a single file fix to the Git repository.
    
    :param repo_path: Path to the Git repository
    :param file_path: Path to the file to commit
    :param issue_description: Description of the issue being fixed (for commit message)
    :return: True if the commit was successful, False otherwise
    """
    try:
        # Get absolute file path
        abs_file_path = Path(file_path).resolve()
        if not abs_file_path.exists():
            raise GitError(f"File does not exist: {abs_file_path}")
        
        # Stage the file
        subprocess.run(
            ['git', 'add', str(abs_file_path)],
            cwd=repo_path,
            capture_output=True,
            check=True,
            text=True
        )
        
        # Create commit
        commit_message = f"fix: Apply pytest-analyzer fix for {issue_description} in {abs_file_path.name}"
        subprocess.run(
            ['git', 'commit', '-m', commit_message],
            cwd=repo_path,
            capture_output=True,
            check=True,
            text=True
        )
        
        logger.info(f"Committed fix for {abs_file_path.name}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error committing fix: {e.stderr}")
        return False

def reset_file(repo_path: str, file_path: str) -> bool:
    """
    Reset a file to its state in the last commit.
    
    :param repo_path: Path to the Git repository
    :param file_path: Path to the file to reset
    :return: True if the reset was successful, False otherwise
    """
    try:
        abs_file_path = Path(file_path).resolve()
        subprocess.run(
            ['git', 'checkout', 'HEAD', '--', str(abs_file_path)],
            cwd=repo_path,
            capture_output=True,
            check=True,
            text=True
        )
        logger.info(f"Reset {abs_file_path.name} to HEAD")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error resetting file: {e.stderr}")
        return False