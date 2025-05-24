"""
Tests to verify the PyQt test environment is set up correctly.

These are basic sanity checks to ensure the test environment can create and interact with widgets.
"""

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget
from pytestqt.plugin import QtBot

from tests.gui.test_utils import click_button_by_text, find_widget, wait_until

# Mark all tests in this module as GUI tests
pytestmark = pytest.mark.gui


def test_create_widget(qtbot: QtBot) -> None:
    """Test that we can create a basic widget."""
    # Create a simple widget
    widget = QWidget()
    widget.setWindowTitle("Test Widget")
    widget.resize(200, 100)

    # Add the widget to qtbot for cleanup
    qtbot.add_widget(widget)

    # Check that the widget has the correct properties
    assert widget.windowTitle() == "Test Widget"
    assert widget.width() == 200
    assert widget.height() == 100


def test_widget_interaction(qtbot: QtBot) -> None:
    """Test that we can interact with widgets using qtbot."""
    # Create a widget with a button
    widget = QWidget()
    layout = QVBoxLayout(widget)

    # Add a label to show the button click
    label = QLabel("Not clicked")
    button = QPushButton("Click me")

    # Set object names for later reference
    label.setObjectName("status_label")
    button.setObjectName("test_button")

    layout.addWidget(label)
    layout.addWidget(button)

    # Connect the button's clicked signal to update the label
    button.clicked.connect(lambda: label.setText("Clicked!"))

    # Add the widget to qtbot for cleanup
    qtbot.add_widget(widget)
    widget.show()

    # Find the button and label using our utility function
    found_button = find_widget(widget, QPushButton, "test_button")
    found_label = find_widget(widget, QLabel, "status_label")

    assert found_button is not None
    assert found_label is not None

    # Click the button using qtbot
    qtbot.mouseClick(found_button, Qt.MouseButton.LeftButton)

    # Check that the label has been updated
    assert found_label.text() == "Clicked!"


def test_utility_functions(qtbot: QtBot) -> None:
    """Test that our utility functions work as expected."""
    # Create a widget with buttons
    widget = QWidget()
    layout = QVBoxLayout(widget)

    # Create buttons with different texts
    button1 = QPushButton("Button 1")
    button2 = QPushButton("Button 2")

    layout.addWidget(button1)
    layout.addWidget(button2)

    # Add attributes to track clicks
    widget._button1_clicked = False
    widget._button2_clicked = False

    button1.clicked.connect(lambda: setattr(widget, "_button1_clicked", True))
    button2.clicked.connect(lambda: setattr(widget, "_button2_clicked", True))

    # Add the widget to qtbot for cleanup
    qtbot.add_widget(widget)
    widget.show()

    # Use click_button_by_text to click Button 2
    result = click_button_by_text(qtbot, widget, "Button 2")

    # Check that the function returned True (button found)
    assert result

    # Check that Button 2 was clicked but not Button 1
    assert not widget._button1_clicked
    assert widget._button2_clicked

    # Reset the clicked state
    widget._button1_clicked = False
    widget._button2_clicked = False

    # Use wait_until to wait for a condition
    button1.clicked.connect(lambda: setattr(widget, "_button1_clicked", True))

    # Start a timer to click the button after a delay
    QTimer.singleShot(100, lambda: qtbot.mouseClick(button1, Qt.MouseButton.LeftButton))

    # Wait until button1_clicked becomes True
    result = wait_until(lambda: widget._button1_clicked, timeout=500)

    # Check that wait_until returned True (condition became true)
    assert result

    # Check that Button 1 was clicked
    assert widget._button1_clicked
