"""
Module for grouping similar test failures together for more efficient analysis.
"""

import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from ..models.pytest_failure import PytestFailure


def _extract_relevant_traceback_frame(
    traceback_str: str, project_root: Optional[str] = None
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Parses a traceback string to find the most relevant frame (often the last one in user code).

    Args:
        traceback_str: The full traceback string.
        project_root: Optional path to the project root to help identify project files.

    Returns:
        A tuple containing (file_path, line_number, function_name) of the relevant frame,
        or (None, None, None) if parsing fails or no relevant frame is found.
    """
    if not traceback_str:
        return None, None, None

    try:
        # Split traceback into lines and filter out irrelevant header/footer lines
        lines = traceback_str.strip().split('\n')
        frame_lines = [line for line in lines if line.strip().startswith('File "')]

        relevant_frame = None
        for i in range(len(frame_lines) - 1, -1, -1):
            line = frame_lines[i].strip()
            # Basic check: Avoid frames inside standard library or site-packages
            if 'site-packages' in line or 'lib/python' in line:
                 # Skip likely pytest internal frames too
                if i + 1 < len(lines) and any(kw in lines[i+1] for kw in ['pytest', '_pytest']):
                    continue 

            # More specific check if project_root is provided
            if project_root and project_root not in line:
                # Only continue if we haven't found any candidate yet
                if relevant_frame is None and i > 0:
                    continue

            match = re.search(r'File "(.+?)", line (\d+), in (\S+)', line)
            if match:
                file_path, line_num_str, func_name = match.groups()
                relevant_frame = (file_path, int(line_num_str), func_name)
                # We want the last frame matching our criteria
                break

        if relevant_frame:
            return relevant_frame
        else:
             # Fallback to the last File line
             if frame_lines:
                 match = re.search(r'File "(.+?)", line (\d+)', frame_lines[-1])
                 if match:
                     return match.group(1), int(match.group(2)), None

    except Exception:
        # Silent failure, returning None values
        pass

    return None, None, None


def extract_failure_fingerprint(failure: PytestFailure, project_root: Optional[str] = None) -> str:
    """
    Generates a fingerprint string for a PytestFailure to group similar errors.

    The fingerprint combines the error type, the error message pattern, and
    (optionally) the affected code component to identify similar failures.
    
    This implementation uses a looser fingerprinting approach to better group 
    similar failures, especially those with the same root cause but appearing
    in different test files.

    Args:
        failure: The PytestFailure object.
        project_root: Optional path to the project root for better frame identification.

    Returns:
        A string fingerprint.
    """
    
    error_type = failure.error_type
    error_message = failure.error_message.split('\n')[0]  # Use first line of message

    # Extract the core components from the error message for better grouping
    # This focuses more on the nature of the error than its exact location
    core_message = ""
    
    if error_type == "AttributeError":
        # Extract the attribute and object information for better grouping
        # Examples:
        # - "module 'foo' has no attribute 'bar'"
        # - "'NoneType' object has no attribute 'baz'"
        
        # Try to extract both the object type and missing attribute
        module_match = re.search(r"module ['\"]([\w.]+)['\"] has no attribute ['\"]([\w.]+)['\"]", error_message)
        if module_match:
            module, attr = module_match.groups()
            # Use just the module name and attribute for grouping
            core_message = f"Module_{module}_Missing_{attr}"
        else:
            # Look for object attribute errors
            obj_match = re.search(r"['\"]([\w.]+)['\"] object has no attribute ['\"]([\w.]+)['\"]", error_message)
            if obj_match:
                obj_type, attr = obj_match.groups()
                # Group by object type and missing attribute
                core_message = f"Type_{obj_type}_Missing_{attr}"
            else:
                # Generic attribute error pattern
                attr_match = re.search(r"no attribute ['\"]([\w.]+)['\"]", error_message)
                if attr_match:
                    attr = attr_match.group(1)
                    # Just group by the missing attribute
                    core_message = f"Missing_{attr}"
                    
                    # For better grouping of similar failures, check if there's a "Did you mean" suggestion
                    mean_match = re.search(r"Did you mean: ['\"]([\w.]+)['\"]", error_message)
                    if mean_match:
                        suggested = mean_match.group(1)
                        # Include the suggested alternative in the fingerprint
                        core_message += f"_DidYouMean_{suggested}"
    
    elif error_type == "ImportError" or error_type == "ModuleNotFoundError":
        # Extract the module name for import errors
        module_match = re.search(r"No module named ['\"]([\w.]+)['\"]", error_message)
        if module_match:
            module = module_match.group(1)
            core_message = f"Missing_Module_{module}"
        else:
            # Handle "cannot import name X from Y"
            import_name_match = re.search(r"cannot import name ['\"]([\w.]+)['\"] from ['\"]([\w.]+)['\"]", error_message)
            if import_name_match:
                name, source = import_name_match.groups()
                core_message = f"Cannot_Import_{name}_From_{source}"
    
    elif error_type == "NameError":
        # Extract the undefined name
        name_match = re.search(r"name ['\"]([\w.]+)['\"] is not defined", error_message)
        if name_match:
            name = name_match.group(1)
            core_message = f"Undefined_{name}"
    
    elif error_type == "TypeError":
        # For type errors, focus on the operation rather than specific values
        # This helps group type errors with the same root cause
        
        # Common TypeError patterns
        if "not callable" in error_message:
            core_message = "NotCallable"
        elif "missing required positional argument" in error_message:
            arg_match = re.search(r"missing required positional argument: ['\"]([\w.]+)['\"]", error_message)
            if arg_match:
                arg = arg_match.group(1)
                core_message = f"Missing_Arg_{arg}"
        elif "takes" in error_message and "arguments" in error_message:
            core_message = "ArgumentCountMismatch"
        elif "unsupported operand type" in error_message:
            core_message = "UnsupportedOperand"
        else:
            # Generic type error grouping
            core_message = error_message[:50].replace(" ", "_")
    
    # If we couldn't extract a meaningful pattern, use a prefix of the error message
    if not core_message:
        # Use up to 30 chars of the error message, normalized
        core_message = re.sub(r'\W+', '_', error_message[:30])
    
    # For better grouping, examine the traceback to find affected module/file
    affected_component = ""
    if failure.traceback:
        # Look for import related file paths in traceback
        file_matches = re.findall(r'File "([^"]+)"', failure.traceback)
        if file_matches:
            for file_path in file_matches:
                # Focus on the affected module/file, not the test file
                if 'tests/' not in file_path and project_root and project_root in file_path:
                    # Extract just the base filename without extension
                    base_name = os.path.basename(file_path)
                    module_name = os.path.splitext(base_name)[0]
                    affected_component = module_name
                    break
    
    # Create the fingerprint components
    fingerprint_parts = [
        error_type,  # Keep the error type
        core_message  # Use our normalized error pattern
    ]
    
    # Add affected component if available (but make it optional)
    if affected_component:
        fingerprint_parts.append(affected_component)
    
    # Generate hash from the fingerprint components
    # Use a simple join rather than a cryptographic hash for better debugging
    fingerprint = "|".join(filter(None, fingerprint_parts))
    
    # For same-type errors in the same file with similar messages, this should produce identical fingerprints
    return fingerprint


def group_failures(
    failures: List[PytestFailure], project_root: Optional[str] = None
) -> Dict[str, List[PytestFailure]]:
    """
    Groups PytestFailure objects based on their extracted fingerprints.

    Args:
        failures: A list of PytestFailure objects.
        project_root: Optional path to the project root for fingerprinting.

    Returns:
        A dictionary where keys are fingerprints and values are lists of
        PytestFailure objects belonging to that group.
    """
    grouped_failures = defaultdict(list)
    for failure in failures:
        fingerprint = extract_failure_fingerprint(failure, project_root)
        failure.group_fingerprint = fingerprint  # Store fingerprint on the object
        grouped_failures[fingerprint].append(failure)
    return dict(grouped_failures)


def select_representative_failure(failure_group: List[PytestFailure]) -> Optional[PytestFailure]:
    """
    Selects the most representative failure from a group of similar failures.

    Current strategy: Select the failure with the most detailed traceback.

    Args:
        failure_group: A list of PytestFailure objects with the same fingerprint.

    Returns:
        The selected representative PytestFailure, or None if the group is empty.
    """
    if not failure_group:
        return None
    
    # Sort by traceback length (descending) - longer tracebacks usually have more context
    sorted_failures = sorted(
        failure_group, 
        key=lambda f: len(f.traceback or '') + (len(f.relevant_code or '') * 2),  # Prioritize code context
        reverse=True
    )
    return sorted_failures[0]