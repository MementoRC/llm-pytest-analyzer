# Pip+Venv Example Project

This directory contains a minimal Pip+Venv project setup.
`pytest-analyzer` may detect this as a Pip+Venv managed environment if a `requirements.txt` file is present, especially if no other specific manager files (like `pyproject.toml` for Poetry/Hatch or `Pipfile`) are found. This is often a fallback detection.

To test this, you would typically create a virtual environment, activate it, and install dependencies:
```bash
# python -m venv .venv
# source .venv/bin/activate  (or .venv\Scripts\activate on Windows)
# pip install -r requirements.txt
```
Then run `pytest-analyzer` from within that activated environment.
