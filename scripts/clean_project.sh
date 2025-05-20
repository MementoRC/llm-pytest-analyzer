#!/bin/bash

# This script helps with project cleanup and management

# Exit on error
set -e

function print_header() {
    echo "=================================================="
    echo "$1"
    echo "=================================================="
}

# First, check if we're in the right directory
if [[ ! -d "src/pytest_analyzer" ]]; then
    echo "ERROR: Please run this script from the project root directory!"
    exit 1
fi

# Clean up Python cache files
print_header "Cleaning Python cache files"
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete
find . -name "*.pyo" -delete
find . -name "*.pyd" -delete
find . -name ".pytest_cache" -exec rm -rf {} +
find . -name ".coverage" -delete
find . -name "htmlcov" -exec rm -rf {} +

# Clean up backup files
print_header "Cleaning backup files"
find . -name "*~" -delete
find . -name "*.bak" -delete
find . -name "*.swp" -delete
find . -name "*.old" -delete
find . -name "*.orig" -delete
find . -name "*.backup" -delete

# Check for any large files
print_header "Checking for large files"
find . -type f -size +1M | grep -v "\.git" | sort -hr

# Show any uncommitted changes
print_header "Uncommitted git changes"
git status

print_header "Cleanup complete!"
echo "Run 'git clean -fd' to remove untracked files and directories (USE WITH CAUTION)"
