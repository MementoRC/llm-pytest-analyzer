import logging
import re
from typing import List, Dict, Any, Optional, Tuple

from ..models.pytest_failure import PytestFailure, FixSuggestion
from ...utils.resource_manager import with_timeout

logger = logging.getLogger(__name__)


class FailureAnalyzer:
    """
    Analyzes test failures and suggests fixes.
    
    This class examines test failures and generates suggestions
    for how to fix the issues based on patterns and heuristics.
    """
    
    def __init__(self, max_suggestions: int = 3):
        """
        Initialize the failure analyzer.
        
        Args:
            max_suggestions: Maximum number of suggestions per failure
        """
        self.max_suggestions = max_suggestions
        
        # Initialize pattern matchers
        self._init_patterns()
        
    def _init_patterns(self):
        """Initialize patterns for matching different types of failures."""
        # Dict mapping error types to analysis functions
        self.error_analyzers = {
            'AssertionError': self._analyze_assertion_error,
            'AttributeError': self._analyze_attribute_error,
            'ImportError': self._analyze_import_error,
            'TypeError': self._analyze_type_error,
            'NameError': self._analyze_name_error,
            'IndexError': self._analyze_index_error,
            'KeyError': self._analyze_key_error,
            'ValueError': self._analyze_value_error,
            'SyntaxError': self._analyze_syntax_error,
        }
        
    @with_timeout(60)
    def analyze_failure(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze a test failure and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        try:
            # Extract the base error type
            base_error_type = self._get_base_error_type(failure.error_type)
            
            # Find the appropriate analyzer function
            analyzer = self.error_analyzers.get(base_error_type, self._analyze_generic_error)
            
            # Generate suggestions
            suggestions = analyzer(failure)
            
            # Limit the number of suggestions
            return suggestions[:self.max_suggestions]
            
        except Exception as e:
            logger.error(f"Error analyzing failure: {e}")
            return []
            
    def _get_base_error_type(self, error_type: str) -> str:
        """
        Extract the base error type from a potentially qualified name.
        
        Args:
            error_type: Error type string
            
        Returns:
            Base error type (e.g., 'AssertionError' from 'unittest.AssertionError')
        """
        # If the error type contains a dot, extract the last part
        if '.' in error_type:
            return error_type.split('.')[-1]
            
        return error_type
        
    def _analyze_assertion_error(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze an assertion error and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Look for common assertion error patterns
        if 'assert' in failure.traceback:
            suggestion, confidence = self._analyze_assert_statement(failure)
            if suggestion:
                suggestions.append(FixSuggestion(
                    failure=failure,
                    suggestion=suggestion,
                    confidence=confidence
                ))
                
        # Generic suggestion if no specific pattern matched
        if not suggestions:
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Review the expected vs. actual values in the assertion.",
                confidence=0.5
            ))
            
        return suggestions
        
    def _analyze_assert_statement(self, failure: PytestFailure) -> Tuple[str, float]:
        """
        Analyze an assert statement and suggest a fix.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            Tuple of (suggestion, confidence)
        """
        # Look for equality assertions
        equality_match = re.search(r'assert\s+([^=]+)\s*==\s*([^,]+)', failure.traceback)
        if equality_match:
            left = equality_match.group(1).strip()
            right = equality_match.group(2).strip()
            
            # Look for expected vs. actual values
            expected_match = re.search(r'E\s+assert\s+([^=]+)\s*==\s*([^,]+)', failure.traceback)
            if expected_match:
                actual = expected_match.group(1).strip()
                expected = expected_match.group(2).strip()
                
                suggestion = f"Change the test to expect {actual} instead of {expected}, or fix the code to return {expected}."
                return suggestion, 0.8
                
            return f"Check why {left} != {right}.", 0.6
            
        # Look for 'in' assertions
        in_match = re.search(r'assert\s+([^\s]+)\s+in\s+([^,]+)', failure.traceback)
        if in_match:
            item = in_match.group(1).strip()
            container = in_match.group(2).strip()
            
            return f"Ensure that {item} is present in {container}.", 0.7
            
        # Look for True/False assertions
        true_match = re.search(r'assert\s+([^,]+)\s*(?:is True)?', failure.traceback)
        if true_match:
            condition = true_match.group(1).strip()
            
            return f"Ensure that {condition} evaluates to True.", 0.6
            
        # No specific pattern matched
        return "", 0.0
        
    def _analyze_attribute_error(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze an attribute error and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Extract the object and attribute
        attr_match = re.search(r"'(.+)'\s+object\s+has\s+no\s+attribute\s+'(.+)'", failure.error_message)
        if attr_match:
            obj_type = attr_match.group(1)
            attribute = attr_match.group(2)
            
            # Check for typos in the attribute name
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Check if '{attribute}' is misspelled or if there's a similar attribute in '{obj_type}'.",
                confidence=0.7
            ))
            
            # Check if the attribute needs to be defined
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Add the '{attribute}' attribute to the '{obj_type}' class.",
                confidence=0.6
            ))
            
        else:
            # Generic suggestion if no specific pattern matched
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Check if the attribute exists and is spelled correctly.",
                confidence=0.5
            ))
            
        return suggestions
        
    def _analyze_import_error(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze an import error and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Extract the module name
        module_match = re.search(r"No module named '(.+)'", failure.error_message)
        if module_match:
            module = module_match.group(1)
            
            # Check if it's a missing module
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Install the '{module}' module with pip or conda.",
                confidence=0.7
            ))
            
            # Check if it's a relative import issue
            if '.' in module:
                suggestions.append(FixSuggestion(
                    failure=failure,
                    suggestion=f"Check the relative import path for '{module}'.",
                    confidence=0.6
                ))
                
        else:
            # Generic suggestion if no specific pattern matched
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Check if the module exists and is in the Python path.",
                confidence=0.5
            ))
            
        return suggestions
        
    def _analyze_type_error(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze a type error and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Check for argument/parameter mismatch
        arg_match = re.search(r"(\w+)\(\) (takes|got)\s+(\d+)\s+(\w+)\s+but\s+(\d+)\s+(\w+)", failure.error_message)
        if arg_match:
            func_name = arg_match.group(1)
            expected = arg_match.group(3)
            actual = arg_match.group(5)
            
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Check the arguments passed to '{func_name}()'. It expected {expected} arguments but got {actual}.",
                confidence=0.8
            ))
            
        # Check for unexpected keyword arguments
        kwarg_match = re.search(r"got an unexpected keyword argument '(.+)'", failure.error_message)
        if kwarg_match:
            param = kwarg_match.group(1)
            
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Remove or rename the '{param}' keyword argument.",
                confidence=0.8
            ))
            
        # Check for "can't multiply sequence by non-int" type errors
        mult_match = re.search(r"can't multiply sequence by non-int of type '(.+)'", failure.error_message)
        if mult_match:
            type_name = mult_match.group(1)
            
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Convert the {type_name} to an integer before using it as a multiplier.",
                confidence=0.7
            ))
            
        # Generic suggestion if no specific pattern matched
        if not suggestions:
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Check the types of the arguments and return values.",
                confidence=0.5
            ))
            
        return suggestions
        
    def _analyze_name_error(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze a name error and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Extract the variable name
        name_match = re.search(r"name '(.+)' is not defined", failure.error_message)
        if name_match:
            var_name = name_match.group(1)
            
            # Check for typos in the variable name
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Check if '{var_name}' is misspelled or if it needs to be defined.",
                confidence=0.7
            ))
            
            # Check if it's an import issue
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Ensure '{var_name}' is imported or defined before use.",
                confidence=0.6
            ))
            
        else:
            # Generic suggestion if no specific pattern matched
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Check if the variable is defined in the current scope.",
                confidence=0.5
            ))
            
        return suggestions
        
    def _analyze_index_error(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze an index error and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Check for list index out of range
        if "list index out of range" in failure.error_message:
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Check the length of the list and ensure the index is within range.",
                confidence=0.7
            ))
            
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Add a bounds check before accessing the list element.",
                confidence=0.6
            ))
            
        else:
            # Generic suggestion if no specific pattern matched
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Check the index and ensure it's within the range of the sequence.",
                confidence=0.5
            ))
            
        return suggestions
        
    def _analyze_key_error(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze a key error and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Extract the key
        key_match = re.search(r"KeyError: '?([^']+)'?", failure.error_message)
        if key_match:
            key = key_match.group(1)
            
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Check if '{key}' exists in the dictionary before accessing it.",
                confidence=0.7
            ))
            
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Use dict.get('{key}', default_value) to provide a default value.",
                confidence=0.6
            ))
            
        else:
            # Generic suggestion if no specific pattern matched
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Check if the key exists in the dictionary before accessing it.",
                confidence=0.5
            ))
            
        return suggestions
        
    def _analyze_value_error(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze a value error and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Check for invalid literal for int()
        int_match = re.search(r"invalid literal for int\(\) with base (\d+): '(.+)'", failure.error_message)
        if int_match:
            base = int_match.group(1)
            value = int_match.group(2)
            
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Ensure '{value}' is a valid integer in base {base}.",
                confidence=0.7
            ))
            
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Add validation or error handling for non-integer inputs.",
                confidence=0.6
            ))
            
        # Generic suggestion if no specific pattern matched
        if not suggestions:
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Check the value being processed and ensure it meets the expected format.",
                confidence=0.5
            ))
            
        return suggestions
        
    def _analyze_syntax_error(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze a syntax error and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Extract the syntax error details
        if "invalid syntax" in failure.error_message:
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Check the syntax at line {failure.line_number}.",
                confidence=0.7
            ))
            
        # Check for common syntax errors
        if failure.relevant_code:
            if '(' in failure.relevant_code and ')' not in failure.relevant_code:
                suggestions.append(FixSuggestion(
                    failure=failure,
                    suggestion="Check for missing closing parenthesis ')'.",
                    confidence=0.8
                ))
                
            if '[' in failure.relevant_code and ']' not in failure.relevant_code:
                suggestions.append(FixSuggestion(
                    failure=failure,
                    suggestion="Check for missing closing bracket ']'.",
                    confidence=0.8
                ))
                
            if '{' in failure.relevant_code and '}' not in failure.relevant_code:
                suggestions.append(FixSuggestion(
                    failure=failure,
                    suggestion="Check for missing closing brace '}'.",
                    confidence=0.8
                ))
                
            if ':' not in failure.relevant_code and ('if ' in failure.relevant_code or 
                                                    'for ' in failure.relevant_code or 
                                                    'while ' in failure.relevant_code or 
                                                    'def ' in failure.relevant_code):
                suggestions.append(FixSuggestion(
                    failure=failure,
                    suggestion="Add a colon ':' at the end of the statement.",
                    confidence=0.8
                ))
                
        # Generic suggestion if no specific pattern matched
        if not suggestions:
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion="Check the syntax of the code.",
                confidence=0.5
            ))
            
        return suggestions
        
    def _analyze_generic_error(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze a generic error and suggest fixes.
        
        Args:
            failure: PytestFailure object to analyze
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Generic suggestion based on error type
        suggestions.append(FixSuggestion(
            failure=failure,
            suggestion=f"Investigate the {failure.error_type} error at line {failure.line_number if failure.line_number else 'unknown'}.",
            confidence=0.5
        ))
        
        # Check if there's relevant code to analyze
        if failure.relevant_code:
            suggestions.append(FixSuggestion(
                failure=failure,
                suggestion=f"Review the code: {failure.relevant_code}",
                confidence=0.4
            ))
            
        return suggestions