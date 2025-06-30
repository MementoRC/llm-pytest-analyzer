"""
ExampleGenerator: Generates code examples for Python objects.

This module provides functionality to generate usage examples for functions, classes, or modules,
optionally using docstring information or AST analysis.

Security: Does not execute user code. Only generates static examples.
"""

import inspect
from typing import Any, Dict, List, Optional


class ExampleGenerationError(Exception):
    """Raised when code example generation fails."""


class ExampleGenerator:
    """
    Generates code examples for Python objects.

    Can use docstring info, type hints, or AST analysis to synthesize examples.
    """

    def __init__(self, docstring_parser=None):
        self.docstring_parser = docstring_parser

    def generate(self, obj: Any, context: Optional[Dict] = None) -> List[str]:
        """
        Generate code examples for a given Python object.

        Args:
            obj: The Python object (function, class, etc.).
            context: Optional context for example generation.

        Returns:
            List of code example strings.
        """
        try:
            if inspect.isfunction(obj) or inspect.ismethod(obj):
                return self._generate_for_function(obj)
            elif inspect.isclass(obj):
                return self._generate_for_class(obj)
            else:
                return []
        except Exception as e:
            raise ExampleGenerationError(f"Failed to generate example: {e}")

    def _generate_for_function(self, func) -> List[str]:
        sig = inspect.signature(func)
        params = []
        for name, param in sig.parameters.items():
            if param.default is not inspect.Parameter.empty:
                params.append(f"{name}={repr(param.default)}")
            elif param.annotation is not inspect.Parameter.empty:
                params.append(f"{name}=<{param.annotation.__name__}>")
            else:
                params.append(f"{name}=<value>")
        call = f"{func.__name__}({', '.join(params)})"
        return [f"# Example usage:\nresult = {call}"]

    def _generate_for_class(self, cls) -> List[str]:
        try:
            init = getattr(cls, "__init__", None)
            if init and inspect.isfunction(init):
                sig = inspect.signature(init)
                params = [name for name in sig.parameters if name != "self"]
                args = ", ".join(f"{name}=<value>" for name in params)
                inst = f"{cls.__name__}({args})"
            else:
                inst = f"{cls.__name__}()"
            return [f"# Example instantiation:\nobj = {inst}"]
        except Exception:
            return [f"# Example instantiation:\nobj = {cls.__name__}()"]
