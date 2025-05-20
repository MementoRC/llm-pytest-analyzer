# Extractor Layer Refactoring

## Overview

This document describes the refactoring of the extractor layer in the pytest-analyzer project. The goal was to establish a more consistent API design across all extractors, improve code reuse, and enhance maintainability.

## Key Changes

1. **Created Base Extractor Class**:
   - Implemented a `BaseExtractor` abstract class that defines the common interface and behavior.
   - Extracted common functionality into the base class to reduce code duplication.
   - Added abstract methods that concrete extractors must implement.

2. **Consistent API Design**:
   - All extractors now implement a consistent `extract()` method that returns a dictionary containing extracted failures and metadata.
   - The method handles different input types (string, Path, dictionary) consistently across all extractors.
   - Maintained backward compatibility with the old `extract_failures()` method.

3. **Improved Error Handling**:
   - Standardized error handling across all extractors.
   - Added proper error propagation and logging.
   - Made error handling more robust and consistent.

4. **Code Duplication Reduction**:
   - Removed duplicated code in the XML and JSON extractors.
   - Created helper methods for handling different input types.
   - Shared common functionality through the base class.

5. **Improved Test Coverage**:
   - Added comprehensive tests for all extractors.
   - Ensured all edge cases are properly tested.
   - Added tests for the new `extract()` method on all extractor types.

6. **Project Management Improvements**:
   - Updated .gitignore to exclude backup files and other artifacts.
   - Added a clean_project.sh script to help with project maintenance.
   - Established better practices for file management.

## Implementation Details

### BaseExtractor Class

The `BaseExtractor` class provides:

- A common `extract()` method that handles different input types.
- A backward-compatible `extract_failures()` method.
- Abstract methods `_do_extract()` and `_extract_from_dict()` that concrete extractors must implement.
- Common helper methods like `_extract_from_path()`.

### Concrete Extractors

1. **XmlResultExtractor**:
   - Refactored to extend `BaseExtractor`.
   - Implemented abstract methods specific to XML parsing.
   - Added specialized extraction from XML elements.

2. **JsonResultExtractor**:
   - Already extended `BaseExtractor`.
   - Added tests for the `extract()` method behavior.
   - Ensured consistent behavior with other extractors.

3. **PytestOutputExtractor**:
   - Refactored to match the API design of other extractors.
   - Added `_extract_from_text()` helper method.
   - Ensured proper error handling.

## Benefits

- **Maintainability**: The code is now more maintainable with clear interfaces and responsibilities.
- **Extensibility**: Adding new extractors is easier with the base class in place.
- **Reliability**: Better error handling and test coverage makes the code more reliable.
- **Readability**: Consistent API design makes the code easier to understand.
- **Scalability**: The architecture can now more easily accommodate new input types or formats.

## Future Considerations

- Add more specialized extractors for different pytest output formats.
- Further consolidate common parsing logic into shared utilities.
- Consider a factory pattern for dynamically selecting the appropriate extractor based on input.
