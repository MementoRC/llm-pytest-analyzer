import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class CodeChangeItem:
    """Represents a code change for a single file."""

    file_path: Path
    fixed_code: str
    original_code: Optional[str] = None
    is_diff_available: bool = field(init=False)
    error_message: Optional[str] = None  # If parsing this item failed

    def __post_init__(self):
        self.is_diff_available = self.original_code is not None


@dataclass
class CodeChangeSet:
    """Parses and holds a set of code changes from a FixSuggestion."""

    items: List[CodeChangeItem] = field(default_factory=list)
    raw_code_changes: Optional[Union[Dict[str, Any], str]] = None
    parsing_error: Optional[str] = None

    @classmethod
    def from_fix_suggestion_changes(
        cls, code_changes_data: Optional[Union[Dict[str, Any], str]]
    ) -> "CodeChangeSet":
        if code_changes_data is None:
            return cls(parsing_error="No code changes provided.")

        items: List[CodeChangeItem] = []
        parsing_error_messages: List[str] = []

        if isinstance(code_changes_data, dict):
            for file_path_str, change_data in code_changes_data.items():
                try:
                    file_path = Path(file_path_str)
                    if isinstance(
                        change_data, str
                    ):  # Simple format: "filepath": "fixed_code_content"
                        items.append(CodeChangeItem(file_path=file_path, fixed_code=change_data))
                    elif isinstance(change_data, dict):  # Structured format
                        original_code = change_data.get("original_code")
                        fixed_code = change_data.get("fixed_code")

                        if fixed_code is None:
                            msg = f"Missing 'fixed_code' for file {file_path_str}."
                            parsing_error_messages.append(msg)
                            items.append(
                                CodeChangeItem(
                                    file_path=file_path, fixed_code="", error_message=msg
                                )
                            )
                            continue
                        if not isinstance(fixed_code, str):
                            msg = f"'fixed_code' for file {file_path_str} is not a string."
                            parsing_error_messages.append(msg)
                            items.append(
                                CodeChangeItem(
                                    file_path=file_path,
                                    fixed_code=str(fixed_code),
                                    error_message=msg,
                                )
                            )
                            continue

                        if original_code is not None and not isinstance(original_code, str):
                            parsing_error_messages.append(
                                f"'original_code' for file {file_path_str} is not a string. Ignoring original_code."
                            )
                            original_code = None

                        items.append(
                            CodeChangeItem(
                                file_path=file_path,
                                fixed_code=fixed_code,
                                original_code=original_code,
                            )
                        )
                    else:
                        msg = f"Unsupported change data type for file {file_path_str}: {type(change_data)}."
                        parsing_error_messages.append(msg)
                        items.append(
                            CodeChangeItem(file_path=file_path, fixed_code="", error_message=msg)
                        )

                except Exception as e:
                    logger.error(
                        f"Error parsing change for file {file_path_str}: {e}", exc_info=True
                    )
                    msg = f"Error parsing change for file {file_path_str}: {e}"
                    parsing_error_messages.append(msg)
                    try:
                        items.append(
                            CodeChangeItem(
                                file_path=Path(file_path_str), fixed_code="", error_message=str(e)
                            )
                        )
                    except Exception:  # If Path(file_path_str) itself fails
                        items.append(
                            CodeChangeItem(
                                file_path=Path("invalid_path"),
                                fixed_code="",
                                error_message=f"Invalid file path string '{file_path_str}': {e}",
                            )
                        )

        elif isinstance(code_changes_data, str):
            # If the entire code_changes_data is a string, we treat it as a raw snippet.
            # The CodeChangeSet will have no items, but raw_code_changes will be set.
            # FixSuggestionCodeView will handle displaying this.
            pass  # No items to parse, but raw_code_changes will be stored.

        else:  # Not None, Not Dict, Not Str
            return cls(
                raw_code_changes=code_changes_data,
                parsing_error=f"Unsupported type for code_changes: {type(code_changes_data)}. Expected Dict or Str.",
            )

        final_parsing_error = "; ".join(parsing_error_messages) if parsing_error_messages else None
        return cls(
            items=items, raw_code_changes=code_changes_data, parsing_error=final_parsing_error
        )
