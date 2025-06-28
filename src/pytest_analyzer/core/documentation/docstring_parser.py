"""
DocstringParser: Extracts and enhances docstrings from Python objects.

This module provides robust parsing of docstrings, supporting Google, NumPy, and reStructuredText styles.
It can extract summaries, parameters, return types, and raise sections, and can enhance docstrings with
additional metadata or formatting.

Security: Only parses trusted source code and does not execute user code.
"""

import inspect
import re
from typing import Any, Dict, Optional


class DocstringParseError(Exception):
    """Raised when a docstring cannot be parsed."""


class DocstringParser:
    """
    Parses and enhances Python docstrings.

    Supports Google, NumPy, and reStructuredText (Sphinx) styles.
    """

    def __init__(self, style: Optional[str] = None):
        self.style = style  # Optionally force a style

    def parse(self, obj: Any) -> Dict[str, Any]:
        """
        Parse the docstring of a Python object.

        Args:
            obj: The Python object (function, class, or module).

        Returns:
            A dictionary with docstring components (summary, params, returns, raises, etc.).
        """
        doc = inspect.getdoc(obj)
        if not doc:
            return {}

        try:
            if self.style == "google" or (
                self.style is None and self._is_google_style(doc)
            ):
                return self._parse_google(doc)
            elif self.style == "numpy" or (
                self.style is None and self._is_numpy_style(doc)
            ):
                return self._parse_numpy(doc)
            else:
                return self._parse_rst(doc)
        except Exception as e:
            raise DocstringParseError(f"Failed to parse docstring: {e}")

    def enhance(
        self, doc_info: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enhance the parsed docstring with additional metadata.

        Args:
            doc_info: Parsed docstring dictionary.
            metadata: Additional metadata to inject.

        Returns:
            Enhanced docstring dictionary.
        """
        if metadata:
            doc_info.update(metadata)
        return doc_info

    def _is_google_style(self, doc: str) -> bool:
        return bool(re.search(r"^\s*Args:", doc, re.MULTILINE))

    def _is_numpy_style(self, doc: str) -> bool:
        return bool(re.search(r"^\s*Parameters\n[-]+", doc, re.MULTILINE))

    def _parse_google(self, doc: str) -> Dict[str, Any]:
        # Simple Google-style parser
        result = {"summary": "", "params": [], "returns": None, "raises": []}
        lines = doc.splitlines()
        state = "summary"
        param_re = re.compile(r"^\s*(\w+)\s*\(([^)]+)\):\s*(.*)")

        for line in lines:
            if line.strip().startswith("Args:"):
                state = "params"
                continue
            elif line.strip().startswith("Returns:"):
                state = "returns"
                continue
            elif line.strip().startswith("Raises:"):
                state = "raises"
                continue

            if state == "summary":
                if line.strip():
                    result["summary"] += line.strip() + " "
            elif state == "params":
                m = param_re.match(line)
                if m:
                    name, typ, desc = m.groups()
                    result["params"].append({"name": name, "type": typ, "desc": desc})
            elif state == "returns":
                if line.strip():
                    result["returns"] = line.strip()
            elif state == "raises":
                if line.strip():
                    result["raises"].append(line.strip())
        result["summary"] = result["summary"].strip()
        return result

    def _parse_numpy(self, doc: str) -> Dict[str, Any]:
        # Simple NumPy-style parser
        result = {"summary": "", "params": [], "returns": None, "raises": []}
        lines = doc.splitlines()
        state = "summary"
        param_section = False
        for i, line in enumerate(lines):
            # Check for section headers (Parameters, Returns, Raises)
            if re.match(r"^\s*Parameters\s*$", line):
                # Check if next line is dashes
                if i + 1 < len(lines) and re.match(r"^\s*-+\s*$", lines[i + 1]):
                    state = "params"
                    param_section = True
                continue
            elif re.match(r"^\s*Returns?\s*$", line):
                # Check if next line is dashes
                if i + 1 < len(lines) and re.match(r"^\s*-+\s*$", lines[i + 1]):
                    state = "returns"
                continue
            elif re.match(r"^\s*Raises?\s*$", line):
                # Check if next line is dashes
                if i + 1 < len(lines) and re.match(r"^\s*-+\s*$", lines[i + 1]):
                    state = "raises"
                continue
            elif re.match(r"^\s*-+\s*$", line):
                # Skip dash lines
                continue

            if state == "summary":
                if line.strip():
                    result["summary"] += line.strip() + " "
            elif state == "params" and param_section:
                m = re.match(r"^\s*(\w+)\s*:\s*([^\n]+)", line)
                if m:
                    name, typ = m.groups()
                    desc = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    result["params"].append({"name": name, "type": typ, "desc": desc})
            elif state == "returns":
                if line.strip():
                    result["returns"] = line.strip()
            elif state == "raises":
                if line.strip():
                    result["raises"].append(line.strip())
        result["summary"] = result["summary"].strip()
        return result

    def _parse_rst(self, doc: str) -> Dict[str, Any]:
        # Simple reStructuredText parser
        result = {"summary": "", "params": [], "returns": None, "raises": []}
        lines = doc.splitlines()
        summary_lines = []
        for line in lines:
            if line.strip().startswith(":param"):
                m = re.match(r":param\s+(\w+):\s*(.*)", line)
                if m:
                    name, desc = m.groups()
                    result["params"].append({"name": name, "type": None, "desc": desc})
            elif line.strip().startswith(":type"):
                m = re.match(r":type\s+(\w+):\s*(.*)", line)
                if m and result["params"]:
                    result["params"][-1]["type"] = m.group(2)
            elif line.strip().startswith(":returns:"):
                m = re.match(r":returns:\s*(.*)", line)
                if m:
                    result["returns"] = m.group(1)
            elif line.strip().startswith(":raises"):
                m = re.match(r":raises\s+(\w+):\s*(.*)", line)
                if m:
                    result["raises"].append(m.group(2))
            else:
                if line.strip():
                    summary_lines.append(line.strip())
        result["summary"] = " ".join(summary_lines).strip()
        return result
