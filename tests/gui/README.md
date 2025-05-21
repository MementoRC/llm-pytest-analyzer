# GUI Testing

This directory contains tests for the Pytest Analyzer GUI components.

## Running the Tests

The GUI tests require a display to run, so they will be skipped automatically if no display is available.

### Local Machine with Display

If you have a graphical environment, you can run the GUI tests with:

```bash
pixi run -e dev pytest tests/gui/
```

### Headless Environment

To run tests in a headless environment (like CI), you need to use a virtual display server like Xvfb:

```bash
# Install Xvfb (on Debian/Ubuntu)
sudo apt-get install xvfb

# Run tests with Xvfb
xvfb-run pixi run -e dev pytest tests/gui/
```

### Skipping GUI Tests

If you want to run all tests except GUI tests, you can use:

```bash
pixi run -e dev pytest -k "not gui"
```

## Test Structure

- `conftest.py` - Contains fixtures for GUI testing
- `test_app.py` - Tests for the PytestAnalyzerApp class
- `test_main_window.py` - Tests for the MainWindow class
- `test_qt_setup.py` - Basic tests to verify PyQt is working correctly
- `test_utils.py` - Utility functions for GUI testing

## Best Practices for GUI Testing

1. **Keep tests independent** - Each test should be able to run on its own
2. **Avoid relying on pixel positions** - Tests should be resilient to screen resolution changes
3. **Clean up resources** - Use qtbot to manage widget lifecycles
4. **Mock external dependencies** - Use monkeypatch to mock file dialogs, etc.
5. **Use proper signals and slots** - Test UI interaction through signals and slots
6. **Test asynchronous operations** - Use waitUntil for testing async operations

## Troubleshooting

If you encounter issues with running tests:

1. **Missing display**: GUI tests require a display server (real or virtual)
2. **QApplication instance already exists**: Make sure only one QApplication is created
3. **Widget not visible**: Use `qtbot.waitExposed(widget)` after showing a widget
4. **Event loop not processing**: Call `QApplication.processEvents()` to process pending events

For more details, see the [pytest-qt documentation](https://pytest-qt.readthedocs.io/).