"""
Tests for DocumentationGenerator class.

Tests the main documentation generation functionality including AST analysis,
docstring parsing integration, example generation, and output formatting.
"""

import ast
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pytest_analyzer.core.documentation import (
    DocumentationGenerationError,
    DocumentationGenerator,
)


class TestDocumentationGenerator:
    """Test suite for DocumentationGenerator class."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            # Create a sample Python module
            sample_module = project_root / "sample_module.py"
            sample_content = '''"""Sample module for testing documentation generation."""

class SampleClass:
    """A sample class for testing.

    Args:
        name: The name of the sample.
        value: An optional value.
    """

    def __init__(self, name: str, value: int = 0):
        self.name = name
        self.value = value

    def get_info(self) -> str:
        """Get information about the sample.

        Returns:
            A string containing sample information.
        """
        return f"{self.name}: {self.value}"

def sample_function(x: int, y: int = 1) -> int:
    """Add two numbers together.

    Args:
        x: First number.
        y: Second number (default: 1).

    Returns:
        The sum of x and y.
    """
    return x + y

SAMPLE_CONSTANT = "test_value"
'''
            sample_module.write_text(sample_content)
            yield project_root

    @pytest.fixture
    def doc_generator(self, temp_project):
        """Create a DocumentationGenerator instance."""
        return DocumentationGenerator(
            project_root=temp_project,
            docstring_style="google",
            include_examples=True,
            include_coverage=True,
        )

    def test_initialization(self, temp_project):
        """Test DocumentationGenerator initialization."""
        generator = DocumentationGenerator(
            project_root=temp_project,
            docstring_style="numpy",
            include_private=True,
            include_examples=False,
            include_coverage=False,
        )

        assert generator.project_root == temp_project
        assert generator.include_private is True
        assert generator.include_examples is False
        assert generator.include_coverage is False
        assert generator.docstring_parser.style == "numpy"

    def test_initialization_defaults(self):
        """Test DocumentationGenerator initialization with defaults."""
        generator = DocumentationGenerator()

        assert generator.project_root == Path.cwd()
        assert generator.include_private is False
        assert generator.include_examples is True
        assert generator.include_coverage is True

    def test_extract_module_structure(self, doc_generator, temp_project):
        """Test AST-based module structure extraction."""
        sample_file = temp_project / "sample_module.py"
        source = sample_file.read_text()
        tree = ast.parse(source)

        structure = doc_generator._extract_module_structure(tree, source)

        assert "classes" in structure
        assert "functions" in structure
        assert "constants" in structure
        assert "imports" in structure

        # Check class extraction
        assert len(structure["classes"]) == 1
        class_info = structure["classes"][0]
        assert class_info["name"] == "SampleClass"
        assert "docstring" in class_info
        assert len(class_info["methods"]) >= 1  # __init__ and get_info

        # Check function extraction
        assert len(structure["functions"]) == 1
        func_info = structure["functions"][0]
        assert func_info["name"] == "sample_function"
        assert "docstring" in func_info
        assert "args" in func_info

        # Check constant extraction
        assert len(structure["constants"]) == 1
        const_info = structure["constants"][0]
        assert const_info["name"] == "SAMPLE_CONSTANT"

    def test_extract_class_info(self, doc_generator):
        """Test extraction of class information from AST."""
        source = '''
class TestClass:
    """Test class docstring."""

    CLASS_VAR = "value"

    def __init__(self):
        pass

    def public_method(self):
        """Public method."""
        pass

    def _private_method(self):
        """Private method."""
        pass
'''
        tree = ast.parse(source)
        class_node = tree.body[0]

        class_info = doc_generator._extract_class_info(class_node, source)

        assert class_info["name"] == "TestClass"
        assert class_info["docstring"] == "Test class docstring."
        assert "CLASS_VAR" in class_info["class_variables"]

        # Should include public method but exclude private when include_private=False
        method_names = [m["name"] for m in class_info["methods"]]
        assert "__init__" in method_names
        assert "public_method" in method_names
        assert "_private_method" not in method_names

    def test_extract_function_info(self, doc_generator):
        """Test extraction of function information from AST."""
        source = '''
@decorator
def test_func(arg1: str, arg2: int = 5) -> bool:
    """Test function docstring."""
    return True
'''
        tree = ast.parse(source)
        func_node = tree.body[0]

        func_info = doc_generator._extract_function_info(func_node, source)

        assert func_info["name"] == "test_func"
        assert func_info["docstring"] == "Test function docstring."
        assert func_info["args"] == ["arg1", "arg2"]
        assert len(func_info["decorators"]) == 1

    def test_should_include_item(self, doc_generator):
        """Test item inclusion logic."""
        # Public items should be included
        assert doc_generator._should_include_item("public_function") is True
        assert doc_generator._should_include_item("PublicClass") is True

        # Private items should be excluded by default
        assert doc_generator._should_include_item("_private_function") is False
        assert doc_generator._should_include_item("__dunder_method__") is False

        # But included when include_private=True
        doc_generator.include_private = True
        assert doc_generator._should_include_item("_private_function") is True

    def test_get_module_docstring(self, doc_generator):
        """Test module docstring extraction."""
        source = '''"""This is a module docstring."""

def some_function():
    pass
'''
        tree = ast.parse(source)
        docstring = doc_generator._get_module_docstring(tree)

        assert docstring == "This is a module docstring."

    def test_generate_module_docs_success(self, doc_generator, temp_project):
        """Test successful module documentation generation."""
        sample_file = temp_project / "sample_module.py"

        docs = doc_generator.generate_module_docs(sample_file)

        assert docs["module_name"] == "sample_module"
        assert "file_path" in docs
        assert "structure" in docs
        assert "docstring" in docs
        assert "classes" in docs
        assert "functions" in docs
        assert "constants" in docs

        # Check that we have the expected content
        assert len(docs["classes"]) == 1
        assert docs["classes"][0]["name"] == "SampleClass"
        assert len(docs["functions"]) == 1
        assert docs["functions"][0]["name"] == "sample_function"
        assert len(docs["constants"]) == 1
        assert docs["constants"][0]["name"] == "SAMPLE_CONSTANT"

    def test_generate_module_docs_file_not_found(self, doc_generator, temp_project):
        """Test module documentation generation with non-existent file."""
        non_existent_file = temp_project / "non_existent.py"

        with pytest.raises(DocumentationGenerationError, match="Module not found"):
            doc_generator.generate_module_docs(non_existent_file)

    def test_generate_module_docs_syntax_error(self, doc_generator, temp_project):
        """Test module documentation generation with syntax error."""
        bad_file = temp_project / "bad_syntax.py"
        bad_file.write_text("def invalid_syntax(\n")  # Intentional syntax error

        with pytest.raises(DocumentationGenerationError):
            doc_generator.generate_module_docs(bad_file)

    @patch(
        "pytest_analyzer.core.documentation.doc_generator.DocumentationGenerator._load_module_from_path"
    )
    def test_generate_class_docs_with_examples(self, mock_load, doc_generator):
        """Test class documentation generation with examples."""
        # Mock a class object
        mock_class = Mock()
        mock_class.__name__ = "MockClass"
        mock_class.__module__ = "test_module"

        mock_load.return_value = mock_class

        class_info = {
            "name": "MockClass",
            "docstring": "Mock class for testing.\n\nArgs:\n    value: Test value.",
            "methods": [],
            "class_variables": [],
        }

        # Mock the example generator
        with patch.object(doc_generator.example_generator, "generate") as mock_gen:
            mock_gen.return_value = ["example = MockClass()"]

            docs = doc_generator._generate_class_docs(class_info, mock_class)

        assert "parsed_docstring" in docs
        assert "examples" in docs
        assert docs["examples"] == ["example = MockClass()"]

    @patch(
        "pytest_analyzer.core.documentation.doc_generator.DocumentationGenerator._load_module_from_path"
    )
    def test_generate_function_docs_with_examples(self, mock_load, doc_generator):
        """Test function documentation generation with examples."""
        # Mock a function object
        mock_func = Mock()
        mock_func.__name__ = "mock_function"
        mock_func.__module__ = "test_module"

        mock_load.return_value = mock_func

        func_info = {
            "name": "mock_function",
            "docstring": "Mock function for testing.\n\nArgs:\n    x: Input value.\n\nReturns:\n    Result.",
            "args": ["x"],
            "returns": None,
            "decorators": [],
        }

        # Mock the example generator
        with patch.object(doc_generator.example_generator, "generate") as mock_gen:
            mock_gen.return_value = ["result = mock_function(x=5)"]

            docs = doc_generator._generate_function_docs(func_info, mock_func)

        assert "parsed_docstring" in docs
        assert "examples" in docs
        assert docs["examples"] == ["result = mock_function(x=5)"]

    def test_generate_project_docs_dict_format(self, doc_generator, temp_project):
        """Test project documentation generation in dict format."""
        docs = doc_generator.generate_project_docs(output_format="dict")

        assert docs["project_name"] == temp_project.name
        assert "modules" in docs
        assert "overview" in docs
        assert "cross_references" in docs
        assert len(docs["modules"]) >= 1

    def test_generate_project_docs_markdown_format(self, doc_generator, temp_project):
        """Test project documentation generation in markdown format."""
        docs = doc_generator.generate_project_docs(output_format="markdown")

        assert isinstance(docs, str)
        assert f"# {temp_project.name}" in docs
        assert "## sample_module" in docs

    def test_generate_project_docs_html_format(self, doc_generator, temp_project):
        """Test project documentation generation in HTML format."""
        docs = doc_generator.generate_project_docs(output_format="html")

        assert isinstance(docs, str)
        assert "<html>" in docs
        assert f"<h1>{temp_project.name}</h1>" in docs
        assert "<h2>sample_module</h2>" in docs

    def test_format_as_markdown(self, doc_generator):
        """Test markdown formatting."""
        docs = {
            "project_name": "TestProject",
            "modules": [
                {
                    "module_name": "test_module",
                    "docstring": "Test module docstring.",
                    "classes": [
                        {"name": "TestClass", "docstring": "Test class docstring."}
                    ],
                }
            ],
        }

        markdown = doc_generator._format_as_markdown(docs)

        assert "# TestProject" in markdown
        assert "## test_module" in markdown
        assert "### Class: TestClass" in markdown
        assert "Test module docstring." in markdown

    def test_format_as_html(self, doc_generator):
        """Test HTML formatting."""
        docs = {
            "project_name": "TestProject",
            "modules": [
                {"module_name": "test_module", "docstring": "Test module docstring."}
            ],
        }

        html = doc_generator._format_as_html(docs)

        assert "<html>" in html
        assert "<h1>TestProject</h1>" in html
        assert "<h2>test_module</h2>" in html
        assert "<p>Test module docstring.</p>" in html

    def test_generate_project_overview(self, doc_generator):
        """Test project overview generation."""
        overview = doc_generator._generate_project_overview()

        assert "description" in overview
        assert "structure" in overview
        assert "total_modules" in overview["structure"]
        assert "total_classes" in overview["structure"]
        assert "total_functions" in overview["structure"]

    def test_generate_cross_references(self, doc_generator):
        """Test cross-reference generation."""
        project_docs = {"modules": []}
        refs = doc_generator._generate_cross_references(project_docs)

        assert "internal_links" in refs
        assert "external_links" in refs
        assert isinstance(refs["internal_links"], list)
        assert isinstance(refs["external_links"], list)

    def test_load_module_from_path_placeholder(self, doc_generator, temp_project):
        """Test the placeholder module loading function."""
        sample_file = temp_project / "sample_module.py"
        result = doc_generator._load_module_from_path(sample_file)

        # Should return None as it's a placeholder implementation
        assert result is None

    def test_extract_constant_info(self, doc_generator):
        """Test constant information extraction."""
        source = "TEST_CONSTANT = 'test_value'"
        tree = ast.parse(source)
        assign_node = tree.body[0]

        const_info = doc_generator._extract_constant_info(assign_node, source)

        assert const_info["name"] == "TEST_CONSTANT"
        assert "line_number" in const_info
        assert "value" in const_info

    def test_docstring_style_integration(self, temp_project):
        """Test integration with different docstring styles."""
        # Test with numpy style
        numpy_generator = DocumentationGenerator(
            project_root=temp_project, docstring_style="numpy"
        )
        assert numpy_generator.docstring_parser.style == "numpy"

        # Test with rst style
        rst_generator = DocumentationGenerator(
            project_root=temp_project, docstring_style="rst"
        )
        assert rst_generator.docstring_parser.style == "rst"

    def test_coverage_integration(self, doc_generator, temp_project):
        """Test integration with coverage analyzer."""
        sample_file = temp_project / "sample_module.py"

        with patch.object(doc_generator.coverage_analyzer, "analyze") as mock_analyze:
            mock_analyze.return_value = {"total": 3, "documented": 2, "coverage": 66.67}

            docs = doc_generator.generate_module_docs(sample_file)

            # Coverage should be included when coverage_analyzer succeeds
            assert "coverage" in docs


class TestDocumentationGeneratorErrorHandling:
    """Test error handling in DocumentationGenerator."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_docstring_parse_error_handling(self, temp_project):
        """Test handling of docstring parse errors."""
        generator = DocumentationGenerator(project_root=temp_project)

        # Mock docstring parser to raise error
        with patch.object(generator.docstring_parser, "parse") as mock_parse:
            mock_parse.side_effect = Exception("Parse error")

            func_info = {
                "name": "test_func",
                "docstring": "Bad docstring",
                "args": [],
                "returns": None,
                "decorators": [],
            }

            docs = generator._generate_function_docs(func_info, None)

            # Should handle error gracefully and provide empty parsed_docstring
            assert "parsed_docstring" in docs
            assert docs["parsed_docstring"] == {}

    def test_example_generation_error_handling(self, temp_project):
        """Test handling of example generation errors."""
        generator = DocumentationGenerator(project_root=temp_project)

        # Mock example generator to raise error
        with patch.object(generator.example_generator, "generate") as mock_generate:
            mock_generate.side_effect = Exception("Generation error")

            func_info = {
                "name": "test_func",
                "docstring": "Test function",
                "args": [],
                "returns": None,
                "decorators": [],
            }

            mock_obj = Mock()
            docs = generator._generate_function_docs(func_info, mock_obj)

            # Should handle error gracefully and provide empty examples
            assert "examples" in docs
            assert docs["examples"] == []

    def test_coverage_analysis_error_handling(self, temp_project):
        """Test handling of coverage analysis errors."""
        generator = DocumentationGenerator(project_root=temp_project)

        sample_file = temp_project / "sample.py"
        sample_file.write_text("def test(): pass")

        # Mock _load_module_from_path to return a mock object so the analyzer gets called
        with patch.object(generator, "_load_module_from_path") as mock_load:
            mock_module = Mock()
            mock_load.return_value = mock_module

            with patch.object(generator.coverage_analyzer, "analyze") as mock_analyze:
                mock_analyze.side_effect = Exception("Coverage error")

                docs = generator.generate_module_docs(sample_file)

                # Should handle error gracefully
                assert "coverage" in docs
                assert "error" in docs["coverage"]
