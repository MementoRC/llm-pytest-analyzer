"""
Utility functions and classes for GUI testing.

This module contains helpers for writing GUI tests.
"""

import time
from typing import Any, Optional, Callable, TypeVar, Type, List, Dict, Union

from PyQt6.QtCore import QObject, Qt, QTimer, QEvent, QPoint
from PyQt6.QtWidgets import QWidget, QApplication, QMainWindow
from pytestqt.plugin import QtBot

T = TypeVar('T', bound=QObject)


def find_widget(parent: QObject, widget_type: Type[T], name: Optional[str] = None) -> Optional[T]:
    """
    Find a widget of a specific type and name among the descendants of parent.
    
    Args:
        parent: The parent widget or object
        widget_type: The type of widget to find
        name: The object name of the widget (optional)
        
    Returns:
        The first matching widget, or None if not found
    """
    for child in parent.findChildren(widget_type):
        if name is None or child.objectName() == name:
            return child
    return None


def wait_until(predicate: Callable[[], bool], timeout: int = 1000, interval: int = 50) -> bool:
    """
    Wait until the predicate becomes true or timeout is reached.
    
    Args:
        predicate: A function that returns a boolean
        timeout: Maximum time to wait in milliseconds
        interval: Polling interval in milliseconds
        
    Returns:
        True if the predicate became true, False if timeout was reached
    """
    deadline = time.time() + timeout / 1000.0
    while time.time() < deadline:
        if predicate():
            return True
        QApplication.processEvents()
        time.sleep(interval / 1000.0)
    return False


def click_button_by_text(qtbot: QtBot, parent: QWidget, text: str) -> bool:
    """
    Click a button identified by its text.
    
    Args:
        qtbot: The QtBot instance
        parent: The parent widget to search in
        text: The text on the button
        
    Returns:
        True if a button was found and clicked, False otherwise
    """
    from PyQt6.QtWidgets import QPushButton
    
    for button in parent.findChildren(QPushButton):
        if button.text() == text and button.isVisible() and button.isEnabled():
            qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
            return True
    return False


def verify_window_state(window: QMainWindow, visible: bool = True) -> bool:
    """
    Verify that a window has the expected visibility state.
    
    Args:
        window: The window to check
        visible: Whether the window should be visible
        
    Returns:
        True if the window's visibility matches the expected state
    """
    return window.isVisible() == visible