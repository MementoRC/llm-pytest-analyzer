import logging
import re
from typing import List

from ...utils.resource_manager import with_timeout
from ..models.pytest_failure import FixSuggestion, PytestFailure

logger = logging.getLogger(__name__)


class FixSuggester:
    """
    Suggests fixes for test failures.

    This class generates concrete code suggestions to fix test failures.
    It uses pattern matching and basic code analysis to suggest changes.
    """

    def __init__(self, min_confidence: float = 0.5):
        """
        Initialize the fix suggester.

        Args:
            min_confidence: Minimum confidence threshold for suggestions
        """
        self.min_confidence = min_confidence

    @with_timeout(60)
    def suggest_fixes(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Suggest fixes for a test failure.

        Args:
            failure: PytestFailure object to analyze

        Returns:
            List of suggested fixes
        """
        try:
            # Generate suggestions based on error type
            suggestions = self._generate_suggestions(failure)

            # Filter suggestions by confidence
            return [s for s in suggestions if s.confidence >= self.min_confidence]

        except Exception as e:
            logger.error(f"Error suggesting fixes: {e}")
            return []

    def _generate_suggestions(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Generate suggestions based on the error type.

        Args:
            failure: PytestFailure object to analyze

        Returns:
            List of suggested fixes
        """
        error_type = failure.error_type

        # Check for exact match first
        if error_type == "AssertionError":
            return self._suggest_assertion_fixes(failure)

        # For other error types, use case-insensitive comparison
        error_type_lower = error_type.lower()

        if "assertion" in error_type_lower:
            return self._suggest_assertion_fixes(failure)
        elif "attribute" in error_type_lower:
            return self._suggest_attribute_fixes(failure)
        elif "import" in error_type_lower:
            return self._suggest_import_fixes(failure)
        elif "type" in error_type_lower:
            return self._suggest_type_fixes(failure)
        elif "name" in error_type_lower:
            return self._suggest_name_fixes(failure)
        elif "syntax" in error_type_lower:
            return self._suggest_syntax_fixes(failure)
        else:
            return self._suggest_generic_fixes(failure)

    def _suggest_assertion_fixes(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Suggest fixes for assertion errors.

        Args:
            failure: PytestFailure object to analyze

        Returns:
            List of suggested fixes
        """
        suggestions = []

        # Extract the actual and expected values from the traceback
        exp_vs_act_match = re.search(
            r"E\s+assert\s+(.+?)\s*==\s*(.+)", failure.traceback
        )
        if exp_vs_act_match:
            actual = exp_vs_act_match.group(1).strip()
            expected = exp_vs_act_match.group(2).strip()

            # Suggest updating the assertion
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Change the assertion to expect {actual} instead of {expected}",
                    confidence=0.7,
                    code_changes={
                        "type": "assertion",
                        "actual": actual,
                        "expected": expected,
                    },
                    explanation=f"The test expected {expected} but got {actual}. If {actual} is the correct value, update the assertion.",
                )
            )

            # Suggest fixing the implementation
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Fix the implementation to return {expected} instead of {actual}",
                    confidence=0.7,
                    code_changes={
                        "type": "implementation",
                        "actual": actual,
                        "expected": expected,
                    },
                    explanation=f"The test expected {expected} but got {actual}. If {expected} is the correct value, update the implementation.",
                )
            )

        # Try to extract from error message if traceback didn't work
        elif "assert" in failure.error_message:
            exp_vs_act_match = re.search(
                r"assert\s+(.+?)\s*==\s*(.+)", failure.error_message
            )
            if exp_vs_act_match:
                actual = exp_vs_act_match.group(1).strip()
                expected = exp_vs_act_match.group(2).strip()

                # Suggest updating the assertion
                suggestions.append(
                    FixSuggestion(
                        failure=failure,
                        suggestion=f"Change the assertion to expect {actual} instead of {expected}",
                        confidence=0.7,
                        code_changes={
                            "type": "assertion",
                            "actual": actual,
                            "expected": expected,
                        },
                        explanation=f"The test expected {expected} but got {actual}. If {actual} is the correct value, update the assertion.",
                    )
                )

                # Suggest fixing the implementation
                suggestions.append(
                    FixSuggestion(
                        failure=failure,
                        suggestion=f"Fix the implementation to return {expected} instead of {actual}",
                        confidence=0.7,
                        code_changes={
                            "type": "implementation",
                            "actual": actual,
                            "expected": expected,
                        },
                        explanation=f"The test expected {expected} but got {actual}. If {expected} is the correct value, update the implementation.",
                    )
                )
            else:
                # Extract the assertion statement
                assert_match = re.search(r"assert\s+(.+)", failure.error_message)
                if assert_match:
                    assertion = assert_match.group(1).strip()

                    suggestions.append(
                        FixSuggestion(
                            failure=failure,
                            suggestion=f"Review the assertion: assert {assertion}",
                            confidence=0.6,
                            code_changes={"type": "assertion", "assertion": assertion},
                            explanation=f"The assertion 'assert {assertion}' failed. Check if the condition is correct.",
                        )
                    )

        # If we still don't have suggestions, look for AssertionError in traceback
        if not suggestions and "AssertionError" in failure.traceback:
            # Extract the assertion statement
            assert_match = re.search(r">\s+assert\s+(.+)", failure.traceback)
            if assert_match:
                assertion = assert_match.group(1).strip()

                suggestions.append(
                    FixSuggestion(
                        failure=failure,
                        suggestion=f"Review the assertion: assert {assertion}",
                        confidence=0.6,
                        code_changes={"type": "assertion", "assertion": assertion},
                        explanation=f"The assertion 'assert {assertion}' failed. Check if the condition is correct.",
                    )
                )

        # Generic fallback if no specific pattern was found
        if not suggestions:
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion="Review the assertion logic in the test",
                    confidence=0.5,
                    explanation="The assertion failed. Review the test logic and the expected values.",
                )
            )

        return suggestions

    def _suggest_attribute_fixes(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Suggest fixes for attribute errors.

        Args:
            failure: PytestFailure object to analyze

        Returns:
            List of suggested fixes
        """
        suggestions = []

        # Extract the object and missing attribute
        attr_match = re.search(
            r"'(.+?)'\s+object\s+has\s+no\s+attribute\s+'(.+?)'", failure.error_message
        )
        if attr_match:
            obj_type = attr_match.group(1)
            attribute = attr_match.group(2)

            # Suggest adding the missing attribute
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Add the '{attribute}' attribute to the '{obj_type}' class",
                    confidence=0.8,
                    code_changes={
                        "type": "add_attribute",
                        "class": obj_type,
                        "attribute": attribute,
                    },
                    explanation=f"The '{obj_type}' class does not have an attribute named '{attribute}'. Add it to the class definition.",
                )
            )

            # Check for similar attributes (common typos)
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Check for similar attributes to '{attribute}' in the '{obj_type}' class",
                    confidence=0.6,
                    explanation=f"The '{attribute}' attribute might be misspelled. Check the '{obj_type}' class for similar attribute names.",
                )
            )

        return suggestions

    def _suggest_import_fixes(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Suggest fixes for import errors.

        Args:
            failure: PytestFailure object to analyze

        Returns:
            List of suggested fixes
        """
        suggestions = []

        # Extract the module name
        module_match = re.search(r"No module named '(.+?)'", failure.error_message)
        if module_match:
            module = module_match.group(1)

            # Suggest installing the module
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Install the '{module}' module",
                    confidence=0.7,
                    code_changes={"type": "install_module", "module": module},
                    explanation=f"The module '{module}' is not installed. Install it using pip or conda.",
                )
            )

            # Suggest adding the correct import path
            if "." in module:
                parent_module = module.split(".")[0]
                suggestions.append(
                    FixSuggestion(
                        failure=failure,
                        suggestion=f"Check the import path for '{module}'",
                        confidence=0.6,
                        code_changes={
                            "type": "fix_import_path",
                            "module": module,
                            "parent_module": parent_module,
                        },
                        explanation=f"The module '{module}' might exist but with a different import path. Check the structure of the '{parent_module}' package.",
                    )
                )

        return suggestions

    def _suggest_type_fixes(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Suggest fixes for type errors.

        Args:
            failure: PytestFailure object to analyze

        Returns:
            List of suggested fixes
        """
        suggestions = []

        # Check for unexpected keyword argument
        kwarg_match = re.search(
            r"got an unexpected keyword argument '(.+?)'", failure.error_message
        )
        if kwarg_match:
            param = kwarg_match.group(1)

            # Suggest removing the unexpected parameter
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Remove the '{param}' parameter",
                    confidence=0.8,
                    code_changes={"type": "remove_parameter", "parameter": param},
                    explanation=f"The function does not accept a parameter named '{param}'. Remove it from the function call.",
                )
            )

            # Suggest checking parameter names
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Check if '{param}' is misspelled",
                    confidence=0.6,
                    explanation=f"The parameter '{param}' might be misspelled. Check the function signature for the correct parameter names.",
                )
            )

        # Check for wrong number of arguments
        arg_match = re.search(
            r"(\w+)\(\) takes (\d+) \w+ but (\d+) \w+ given", failure.error_message
        )
        if arg_match:
            func_name = arg_match.group(1)
            expected = arg_match.group(2)
            actual = arg_match.group(3)

            # Suggest fixing the number of arguments
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Adjust the number of arguments to {func_name}()",
                    confidence=0.8,
                    code_changes={
                        "type": "fix_argument_count",
                        "function": func_name,
                        "expected": expected,
                        "actual": actual,
                    },
                    explanation=f"The function '{func_name}()' expects {expected} arguments but {actual} were given. Adjust the function call.",
                )
            )

        return suggestions

    def _suggest_name_fixes(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Suggest fixes for name errors.

        Args:
            failure: PytestFailure object to analyze

        Returns:
            List of suggested fixes
        """
        suggestions = []

        # Extract the undefined name
        name_match = re.search(r"name '(.+?)' is not defined", failure.error_message)
        if name_match:
            var_name = name_match.group(1)

            # Suggest defining the variable
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Define the variable '{var_name}' before using it",
                    confidence=0.7,
                    code_changes={"type": "define_variable", "variable": var_name},
                    explanation=f"The variable '{var_name}' is used but not defined. Define it before use.",
                )
            )

            # Suggest importing the name
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Import '{var_name}' if it's from another module",
                    confidence=0.6,
                    code_changes={"type": "import_name", "name": var_name},
                    explanation=f"The name '{var_name}' might be defined in another module. Add an import statement.",
                )
            )

            # Suggest checking for typos
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Check if '{var_name}' is misspelled",
                    confidence=0.5,
                    explanation=f"The variable '{var_name}' might be misspelled. Check for similar variable names in the code.",
                )
            )

        return suggestions

    def _suggest_syntax_fixes(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Suggest fixes for syntax errors.

        Args:
            failure: PytestFailure object to analyze

        Returns:
            List of suggested fixes
        """
        suggestions = []

        # Placeholder for code context
        code_context = failure.relevant_code or ""

        # Check for missing parentheses
        if "(" in code_context and ")" not in code_context:
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion="Add a missing closing parenthesis ')'",
                    confidence=0.7,
                    code_changes={"type": "add_character", "character": ")"},
                    explanation="There appears to be a missing closing parenthesis in the code.",
                )
            )

        # Check for missing brackets
        elif "[" in code_context and "]" not in code_context:
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion="Add a missing closing bracket ']'",
                    confidence=0.7,
                    code_changes={"type": "add_character", "character": "]"},
                    explanation="There appears to be a missing closing bracket in the code.",
                )
            )

        # Check for missing braces
        elif "{" in code_context and "}" not in code_context:
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion="Add a missing closing brace '}'",
                    confidence=0.7,
                    code_changes={"type": "add_character", "character": "}"},
                    explanation="There appears to be a missing closing brace in the code.",
                )
            )

        # Check for missing colons
        elif any(
            keyword in code_context
            for keyword in ["if", "else", "elif", "for", "while", "def", "class"]
        ) and not code_context.strip().endswith(":"):
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion="Add a missing colon ':' at the end of the statement",
                    confidence=0.7,
                    code_changes={"type": "add_character", "character": ":"},
                    explanation="Python statements like 'if', 'for', 'def', etc. require a colon at the end.",
                )
            )

        # Generic syntax error suggestion
        if not suggestions:
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Fix the syntax error at line {failure.line_number}",
                    confidence=0.5,
                    explanation="There is a syntax error in the code. Check the syntax carefully.",
                )
            )

        return suggestions

    def _suggest_generic_fixes(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Suggest fixes for generic errors.

        Args:
            failure: PytestFailure object to analyze

        Returns:
            List of suggested fixes
        """
        suggestions = []

        # Generic suggestion based on error type
        suggestions.append(
            FixSuggestion(
                failure=failure,
                suggestion=f"Fix the {failure.error_type} error",
                confidence=0.5,
                explanation=f"There is a {failure.error_type} error in the code. Review the error message and traceback for more information.",
            )
        )

        # If we have a line number, add a more specific suggestion
        if failure.line_number:
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=f"Check line {failure.line_number} in {failure.test_file}",
                    confidence=0.6,
                    explanation=f"The error is located at line {failure.line_number} in {failure.test_file}.",
                )
            )

        return suggestions
