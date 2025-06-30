"""
CrossReferencer: Handles cross-references and links in documentation.

This module provides utilities to resolve, validate, and format cross-references between
Python objects, modules, and external documentation.

Security: Does not follow or resolve untrusted URLs.
"""

from typing import Any, Optional


class CrossReferenceError(Exception):
    """Raised when a cross-reference cannot be resolved."""


class CrossReferencer:
    """
    Handles cross-references and links in documentation.

    Can resolve references to other objects, modules, or external docs.
    """

    def __init__(self, root_module: Optional[Any] = None):
        self.root_module = root_module

    def resolve(self, ref: str, context: Optional[Any] = None) -> Optional[str]:
        """
        Resolve a cross-reference to a fully qualified name or URL.

        Args:
            ref: The reference string (e.g., "os.path.join").
            context: Optional context/module for relative resolution.

        Returns:
            The fully qualified name or URL, or None if not found.
        """
        try:
            if self.root_module and hasattr(self.root_module, ref):
                obj = getattr(self.root_module, ref)
                return f"{obj.__module__}.{obj.__name__}"
            elif context and hasattr(context, ref):
                obj = getattr(context, ref)
                return f"{obj.__module__}.{obj.__name__}"
            else:
                # Fallback: treat as external or unresolved
                return None
        except Exception:
            return None

    def format_link(self, ref: str, url_template: Optional[str] = None) -> str:
        """
        Format a cross-reference as a documentation link.

        Args:
            ref: The reference string.
            url_template: Optional URL template (e.g., "https://docs.python.org/3/library/{ref}.html").

        Returns:
            A formatted link string.
        """
        if url_template:
            safe_ref = ref.replace(".", "/")
            return url_template.format(ref=safe_ref)
        return ref
