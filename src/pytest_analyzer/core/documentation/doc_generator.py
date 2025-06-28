"""
DocumentationGenerator: Main class for comprehensive documentation generation.

This module provides the primary interface for generating comprehensive documentation
from Python source code, coordinating all documentation generation components.

Security: Only analyzes trusted source code and does not execute user code.
"""

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .coverage_analyzer import CoverageAnalyzer, CoverageAnalyzerError
from .cross_referencer import CrossReferencer
from .docstring_parser import DocstringParseError, DocstringParser
from .example_generator import ExampleGenerationError, ExampleGenerator


class DocumentationGenerationError(Exception):
    """Raised when documentation generation fails."""


class DocumentationGenerator:
    """
    Comprehensive documentation generator for Python projects.

    Coordinates AST analysis, docstring parsing, example generation,
    coverage analysis, and cross-referencing to produce complete documentation.
    """

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        docstring_style: Optional[str] = None,
        include_private: bool = False,
        include_examples: bool = True,
        include_coverage: bool = True,
    ):
        """
        Initialize the documentation generator.

        Args:
            project_root: Root directory of the project to document.
            docstring_style: Preferred docstring style ('google', 'numpy', 'rst').
            include_private: Whether to include private methods/functions.
            include_examples: Whether to generate code examples.
            include_coverage: Whether to include coverage analysis.
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.include_private = include_private
        self.include_examples = include_examples
        self.include_coverage = include_coverage

        # Initialize component analyzers
        self.docstring_parser = DocstringParser(style=docstring_style)
        self.example_generator = ExampleGenerator(
            docstring_parser=self.docstring_parser
        )
        self.cross_referencer = CrossReferencer()
        self.coverage_analyzer = CoverageAnalyzer(
            docstring_parser=self.docstring_parser
        )

    def generate_module_docs(self, module_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Generate comprehensive documentation for a Python module.

        Args:
            module_path: Path to the Python module file.

        Returns:
            Complete documentation dictionary for the module.

        Raises:
            DocumentationGenerationError: If documentation generation fails.
        """
        try:
            module_path = Path(module_path)
            if not module_path.exists():
                raise DocumentationGenerationError(f"Module not found: {module_path}")

            # Parse the module AST
            with open(module_path, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(module_path))

            # Extract module structure
            module_info = self._extract_module_structure(tree, source)

            # Load the module for runtime inspection
            try:
                spec = self._load_module_from_path(module_path)
                module_obj = spec if spec else None
            except Exception:
                module_obj = None

            # Generate documentation sections
            docs = {
                "module_name": module_path.stem,
                "file_path": str(module_path.relative_to(self.project_root)),
                "structure": module_info,
                "docstring": self._get_module_docstring(tree),
                "classes": [],
                "functions": [],
                "constants": [],
            }

            # Process classes
            for class_info in module_info.get("classes", []):
                class_docs = self._generate_class_docs(class_info, module_obj)
                docs["classes"].append(class_docs)

            # Process functions
            for func_info in module_info.get("functions", []):
                func_docs = self._generate_function_docs(func_info, module_obj)
                docs["functions"].append(func_docs)

            # Process constants/variables
            for const_info in module_info.get("constants", []):
                const_docs = self._generate_constant_docs(const_info, module_obj)
                docs["constants"].append(const_docs)

            # Add coverage analysis if enabled
            if self.include_coverage:
                try:
                    # For now, always try to analyze even without module_obj
                    # The analyzer can work with the structure we extracted
                    if module_obj:
                        coverage = self.coverage_analyzer.analyze(module_obj)
                    else:
                        # Provide basic coverage info from structure
                        total_items = len(docs["classes"]) + len(docs["functions"])
                        documented_items = sum(
                            1
                            for item in docs["classes"] + docs["functions"]
                            if item.get("docstring")
                        )
                        coverage = {
                            "total": total_items,
                            "documented": documented_items,
                            "coverage": (documented_items / total_items * 100)
                            if total_items > 0
                            else 100.0,
                        }
                    docs["coverage"] = coverage
                except (CoverageAnalyzerError, Exception) as e:
                    docs["coverage"] = {"error": str(e)}

            return docs

        except Exception as e:
            raise DocumentationGenerationError(
                f"Failed to generate docs for {module_path}: {e}"
            )

    def generate_project_docs(
        self, output_format: str = "dict"
    ) -> Union[Dict[str, Any], str]:
        """
        Generate documentation for the entire project.

        Args:
            output_format: Output format ('dict', 'markdown', 'html').

        Returns:
            Complete project documentation in the specified format.

        Raises:
            DocumentationGenerationError: If project documentation generation fails.
        """
        try:
            project_docs = {
                "project_name": self.project_root.name,
                "project_root": str(self.project_root),
                "modules": [],
                "overview": self._generate_project_overview(),
            }

            # Find all Python modules in the project
            python_files = list(self.project_root.rglob("*.py"))

            for py_file in python_files:
                # Skip __pycache__ and other non-source directories
                if "__pycache__" in str(py_file) or ".git" in str(py_file):
                    continue

                try:
                    module_docs = self.generate_module_docs(py_file)
                    project_docs["modules"].append(module_docs)
                except DocumentationGenerationError:
                    # Log but continue with other modules
                    continue

            # Add cross-references
            project_docs["cross_references"] = self._generate_cross_references(
                project_docs
            )

            # Format output
            if output_format == "markdown":
                return self._format_as_markdown(project_docs)
            elif output_format == "html":
                return self._format_as_html(project_docs)
            else:
                return project_docs

        except Exception as e:
            raise DocumentationGenerationError(f"Failed to generate project docs: {e}")

    def _extract_module_structure(self, tree: ast.AST, source: str) -> Dict[str, Any]:
        """Extract the structural information from a module AST."""
        structure = {
            "classes": [],
            "functions": [],
            "constants": [],
            "imports": [],
        }

        # Only process top-level nodes, not nested ones
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if self._should_include_item(node.name):
                    class_info = self._extract_class_info(node, source)
                    structure["classes"].append(class_info)

            elif isinstance(node, ast.FunctionDef):
                if self._should_include_item(node.name):
                    func_info = self._extract_function_info(node, source)
                    structure["functions"].append(func_info)

            elif isinstance(node, ast.Assign):
                # Extract module-level constants
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        const_info = self._extract_constant_info(node, source)
                        structure["constants"].append(const_info)

        return structure

    def _extract_class_info(self, node: ast.ClassDef, source: str) -> Dict[str, Any]:
        """Extract information about a class from its AST node."""
        return {
            "name": node.name,
            "line_number": node.lineno,
            "docstring": ast.get_docstring(node),
            "methods": [
                self._extract_function_info(child, source)
                for child in node.body
                if isinstance(child, ast.FunctionDef)
                and self._should_include_method(child.name)
            ],
            "class_variables": [
                target.id
                for child in node.body
                if isinstance(child, ast.Assign)
                for target in child.targets
                if isinstance(target, ast.Name)
            ],
        }

    def _extract_function_info(
        self, node: ast.FunctionDef, source: str
    ) -> Dict[str, Any]:
        """Extract information about a function from its AST node."""
        return {
            "name": node.name,
            "line_number": node.lineno,
            "docstring": ast.get_docstring(node),
            "args": [arg.arg for arg in node.args.args],
            "returns": getattr(node, "returns", None),
            "decorators": [
                ast.unparse(decorator) if hasattr(ast, "unparse") else str(decorator)
                for decorator in node.decorator_list
            ],
        }

    def _extract_constant_info(self, node: ast.Assign, source: str) -> Dict[str, Any]:
        """Extract information about a constant from its AST node."""
        target = node.targets[0]
        if isinstance(target, ast.Name):
            return {
                "name": target.id,
                "line_number": node.lineno,
                "value": ast.unparse(node.value)
                if hasattr(ast, "unparse")
                else str(node.value),
            }
        return {}

    def _should_include_item(self, name: str) -> bool:
        """Determine if an item should be included in documentation."""
        if not self.include_private and name.startswith("_"):
            return False
        return True

    def _should_include_method(self, name: str) -> bool:
        """Determine if a method should be included in documentation."""
        # Always include __init__ and other special methods
        if name in ("__init__", "__new__", "__str__", "__repr__"):
            return True
        # Use normal private method logic for others
        return self._should_include_item(name)

    def _get_module_docstring(self, tree: ast.AST) -> Optional[str]:
        """Extract the module-level docstring."""
        return ast.get_docstring(tree)

    def _generate_class_docs(
        self, class_info: Dict[str, Any], module_obj: Any
    ) -> Dict[str, Any]:
        """Generate complete documentation for a class."""
        docs = dict(class_info)

        # Parse docstring
        if class_info.get("docstring"):
            try:
                parsed_docstring = self.docstring_parser.parse(class_info["docstring"])
                docs["parsed_docstring"] = parsed_docstring
            except (DocstringParseError, Exception):
                docs["parsed_docstring"] = {}

        # Generate examples if enabled
        if self.include_examples and module_obj:
            try:
                class_obj = getattr(module_obj, class_info["name"], None)
                if class_obj:
                    examples = self.example_generator.generate(class_obj)
                    docs["examples"] = examples
            except (ExampleGenerationError, AttributeError, Exception):
                docs["examples"] = []

        # Process methods
        method_docs = []
        for method_info in class_info.get("methods", []):
            method_docs.append(self._generate_function_docs(method_info, module_obj))
        docs["methods"] = method_docs

        return docs

    def _generate_function_docs(
        self, func_info: Dict[str, Any], module_obj: Any
    ) -> Dict[str, Any]:
        """Generate complete documentation for a function."""
        docs = dict(func_info)

        # Parse docstring
        if func_info.get("docstring"):
            try:
                parsed_docstring = self.docstring_parser.parse(func_info["docstring"])
                docs["parsed_docstring"] = parsed_docstring
            except (DocstringParseError, Exception):
                docs["parsed_docstring"] = {}

        # Generate examples if enabled
        if self.include_examples and module_obj:
            try:
                func_obj = getattr(module_obj, func_info["name"], None)
                if func_obj:
                    examples = self.example_generator.generate(func_obj)
                    docs["examples"] = examples
            except (ExampleGenerationError, AttributeError, Exception):
                docs["examples"] = []

        return docs

    def _generate_constant_docs(
        self, const_info: Dict[str, Any], module_obj: Any
    ) -> Dict[str, Any]:
        """Generate documentation for a constant."""
        return dict(const_info)

    def _generate_project_overview(self) -> Dict[str, Any]:
        """Generate a high-level overview of the project."""
        return {
            "description": "Auto-generated project documentation",
            "structure": {
                "total_modules": 0,
                "total_classes": 0,
                "total_functions": 0,
            },
        }

    def _generate_cross_references(
        self, project_docs: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Generate cross-references between project components."""
        return {
            "internal_links": [],
            "external_links": [],
        }

    def _load_module_from_path(self, module_path: Path) -> Optional[Any]:
        """Safely load a module from a file path for inspection."""
        # This is a placeholder - actual implementation would need
        # proper module loading with import safety
        return None

    def _format_as_markdown(self, docs: Dict[str, Any]) -> str:
        """Format documentation as Markdown."""
        md_lines = [f"# {docs['project_name']}\n"]

        for module in docs.get("modules", []):
            md_lines.append(f"## {module['module_name']}\n")
            if module.get("docstring"):
                md_lines.append(f"{module['docstring']}\n")

            for cls in module.get("classes", []):
                md_lines.append(f"### Class: {cls['name']}\n")
                if cls.get("docstring"):
                    md_lines.append(f"{cls['docstring']}\n")

        return "\n".join(md_lines)

    def _format_as_html(self, docs: Dict[str, Any]) -> str:
        """Format documentation as HTML."""
        html_parts = [
            f"<html><head><title>{docs['project_name']}</title></head><body>",
            f"<h1>{docs['project_name']}</h1>",
        ]

        for module in docs.get("modules", []):
            html_parts.append(f"<h2>{module['module_name']}</h2>")
            if module.get("docstring"):
                html_parts.append(f"<p>{module['docstring']}</p>")

        html_parts.append("</body></html>")
        return "\n".join(html_parts)
