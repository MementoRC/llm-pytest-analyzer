# Pytest Analyzer GUI Design Document

## Overview

The Pytest Analyzer GUI provides a user-friendly interface for analyzing pytest test failures, visualizing the results, and implementing suggested fixes. The GUI complements the existing CLI functionality while making it more accessible to users who prefer graphical interfaces.

## Main Components

The GUI will consist of the following key components:

1. **Main Window** - The primary application window with a menu bar, toolbar, and status bar
2. **Test Selection Panel** - For selecting test files or directories
3. **Failure Analysis View** - Displays test failures, groupings, and patterns
4. **Fix Suggestion Panel** - Shows LLM-generated fix suggestions 
5. **Code Editor** - For reviewing and editing suggested fixes
6. **Settings Dialog** - For configuring the application

## Layout Wireframes

### Main Window Layout

```
+----------------------------------------------------------------------+
| File  Edit  View  Tools  Help                                         |
+----------------------------------------------------------------------+
| [Open] [Run] [Stop] [Settings]                        [LLM Provider] |
+----------------------------------------------------------------------+
|                        |                                              |
| Test Selection         | Failure Analysis View                        |
| +------------------+   | +------------------------------------------+ |
| | Project Files    |   | | Test Failures (2)                      v | |
| | +--------------+ |   | | +---------------------------------+      | |
| | | test_module.py|   | | | test_module.py::test_function_1  |      | |
| | | +-test_func_1 |   | | | Error: AssertionError           |      | |
| | | +-test_func_2 |   | | | Group: API Response Validation  |      | |
| | | another_test..|   | | +---------------------------------+      | |
| | +--------------+ |   | |                                          | |
| +------------------+   | | +---------------------------------+      | |
|                        | | | test_module.py::test_function_2  |      | |
| [Load Test Results]    | | | Error: TypeError                 |      | |
|                        | | | Group: Type Conversion           |      | |
|                        | | +---------------------------------+      | |
|                        | +------------------------------------------+ |
|                        |                                              |
|                        | Fix Suggestion                               |
|                        | +------------------------------------------+ |
|                        | | The issue appears to be in the API       | |
|                        | | response validation where expected and   | |
|                        | | actual values don't match.              | |
|                        | |                                          | |
|                        | | Suggested fix:                           | |
|                        | | ```python                                | |
|                        | | # Change line 42 from:                   | |
|                        | | assert response.status == 200            | |
|                        | | # To:                                    | |
|                        | | assert response.status_code == 200       | |
|                        | | ```                                      | |
|                        | |                                          | |
|                        | | [Show Diff] [Apply Fix] [Skip]           | |
|                        | +------------------------------------------+ |
+----------------------------------------------------------------------+
| Ready | LLM: GPT-4 | Analyzing 2 test failures                        |
+----------------------------------------------------------------------+
```

### Settings Dialog

```
+----------------------------------------------------------------------+
| Settings                                                [X] [?]      |
+----------------------------------------------------------------------+
| General                                                              |
| +------------------------------------------------------------------+ |
| | Project Root: [/path/to/project                     ] [Browse..] | |
| | Default Test Directory: [tests/                     ] [Browse..] | |
| | Auto-run Failed Tests: [X]                                       | |
| | Max Test Runs: [3      ]                                         | |
| +------------------------------------------------------------------+ |
|                                                                      |
| LLM Configuration                                                    |
| +------------------------------------------------------------------+ |
| | Provider:      [OpenAI▼]                                         | |
| | Model:         [gpt-4▼ ]                                         | |
| | API Key:       [****************************************]         | |
| | Temperature:   [0.7    ]                                         | |
| | Max Tokens:    [4096   ]                                         | |
| | Stream Output: [X]                                               | |
| +------------------------------------------------------------------+ |
|                                                                      |
| Git Integration                                                      |
| +------------------------------------------------------------------+ |
| | Use Git Integration: [X]                                         | |
| | Auto-create Branches: [X]                                        | |
| | Branch Prefix: [fix-  ]                                          | |
| | Auto-commit Fixes: [ ]                                           | |
| +------------------------------------------------------------------+ |
|                                                                      |
|                                            [Cancel] [Save & Close]   |
+----------------------------------------------------------------------+
```

### Code Editor View

```
+----------------------------------------------------------------------+
| Code Editor - test_module.py                              [X] [?]    |
+----------------------------------------------------------------------+
| 38  def test_function_1():                                           |
| 39      """Test that the API response is validated correctly."""     |
| 40      response = make_api_call()                                   |
| 41                                                                   |
| 42*     assert response.status == 200  # This line will be changed   |
| 43      assert response.json()["data"] is not None                   |
| 44      assert "id" in response.json()["data"]                       |
+----------------------------------------------------------------------+
| Diff View                                                           |
| +------------------------------------------------------------------+ |
| | - assert response.status == 200                                  | |
| | + assert response.status_code == 200                             | |
| +------------------------------------------------------------------+ |
|                                                                      |
|                                    [Cancel] [Apply] [Apply & Close]  |
+----------------------------------------------------------------------+
```

## Interaction Flow

1. **Starting the Application**:
   - User launches the pytest-analyzer-gui
   - Main window appears with empty panels
   - User can select a project or load test results

2. **Loading Test Results**:
   - User selects a test file/directory or loads existing test results
   - Application displays available tests in the Test Selection panel
   - Failures and errors are shown in the Failure Analysis View

3. **Analyzing Failures**:
   - User selects a failure from the Failure Analysis View
   - Application sends the failure information to the LLM for analysis
   - Progress is shown in the status bar
   - Fix suggestions are displayed in the Fix Suggestion panel

4. **Applying Fixes**:
   - User reviews the suggested fix
   - Clicks "Show Diff" to see the proposed changes in the Code Editor
   - Can apply the fix directly or edit it before applying
   - Application can optionally run the test again to verify the fix

5. **Configuration**:
   - User accesses Settings dialog from menu or toolbar
   - Can configure LLM provider, project settings, and Git integration

## Implementation Details

### Key Classes

1. `MainWindow` - The primary application window and controller
2. `TestModel` - Data model for test information
3. `FailureModel` - Data model for failure information
4. `TestSelectionView` - UI component for test selection
5. `FailureAnalysisView` - UI component for failure display
6. `FixSuggestionView` - UI component for fix suggestions
7. `CodeEditorView` - UI component for code editing
8. `SettingsDialog` - Dialog for application configuration
9. `AnalyzerService` - Interface to the core pytest-analyzer functionality

### Technology Stack

- **PyQt6**: UI framework
- **Rich**: Terminal-like output formatting in the GUI
- **Qt Designer**: For creating and editing UI layouts
- **Pytest Analyzer Core**: Existing functionality for test analysis

## Integration with Existing Code

The GUI will be implemented as a new component that uses the existing pytest-analyzer core functionality. It will:

1. Import and use the `PytestAnalyzerService` class for core functionality
2. Use the same models and data structures as the CLI
3. Share configuration with the CLI through the `Settings` class
4. Maintain backward compatibility with the CLI

## Future Enhancements

- **Result History**: Save and load previous analysis sessions
- **Batch Processing**: Analyze and fix multiple failures in one operation
- **Interactive Tutorials**: Guide users through the analysis process
- **Custom Themes**: Light/dark mode and customizable UI themes
- **Plugin System**: Allow extensions for specialized test frameworks