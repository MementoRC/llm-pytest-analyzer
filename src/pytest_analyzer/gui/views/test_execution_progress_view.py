import logging
from typing import Optional

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class TestExecutionProgressView(QWidget):
    """
    View for displaying test execution progress.
    """

    cancel_requested = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        logger.debug("TestExecutionProgressView: Initializing.")
        self._init_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_elapsed_time)
        self._elapsed_seconds = 0
        self.reset_view()
        logger.debug("TestExecutionProgressView: Initialization complete and view reset.")

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        logger.debug("TestExecutionProgressView: Initializing UI.")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Progress Bar and Percentage
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        progress_layout.addWidget(self.progress_bar, 1)

        self.percentage_label = QLabel("0%")
        self.percentage_label.setFixedWidth(40)
        self.percentage_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        progress_layout.addWidget(self.percentage_label)
        main_layout.addLayout(progress_layout)

        # Status Message (Current Test / Overall Status)
        self.status_message_label = QLabel("Status: Idle")
        self.status_message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        main_layout.addWidget(self.status_message_label)

        # Stats and Time
        stats_time_layout = QGridLayout()

        self.passed_label = QLabel("Passed: 0")
        stats_time_layout.addWidget(self.passed_label, 0, 0)

        self.failed_label = QLabel("Failed: 0")
        stats_time_layout.addWidget(self.failed_label, 0, 1)

        self.skipped_label = QLabel("Skipped: 0")
        stats_time_layout.addWidget(self.skipped_label, 0, 2)

        self.errors_label = QLabel("Errors: 0")  # Pytest distinguishes failures and errors
        stats_time_layout.addWidget(self.errors_label, 0, 3)

        stats_time_layout.addItem(
            QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum), 0, 4
        )

        self.elapsed_time_label = QLabel("Elapsed: 00:00")
        stats_time_layout.addWidget(self.elapsed_time_label, 1, 0, 1, 2)

        self.remaining_time_label = QLabel("Remaining: N/A")  # Placeholder
        stats_time_layout.addWidget(self.remaining_time_label, 1, 2, 1, 2)

        stats_time_layout.addItem(
            QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum), 1, 4
        )

        main_layout.addLayout(stats_time_layout)

        # Cancel Button
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.cancel_button = QPushButton("Cancel Execution")
        self.cancel_button.clicked.connect(self._emit_cancel_requested_debug)  # Changed connection
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        # Add a frame for visual separation
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)  # or HLine, VLine
        frame.setLayout(main_layout)

        outer_layout = QVBoxLayout()
        outer_layout.addWidget(frame)
        self.setLayout(outer_layout)
        logger.debug("TestExecutionProgressView: UI initialized.")

    def _emit_cancel_requested_debug(self):  # New method
        logger.debug(
            "TestExecutionProgressView: Cancel button clicked. Emitting cancel_requested signal."
        )
        self.cancel_requested.emit()

    def update_progress(self, percentage: int, message: Optional[str] = None) -> None:
        """Update the progress bar and percentage label."""
        logger.debug(
            f"TestExecutionProgressView: Updating progress. Percentage: {percentage}%, Message: '{message}'."
        )
        self.progress_bar.setValue(percentage)
        self.percentage_label.setText(f"{percentage}%")
        if message:
            self.status_message_label.setText(f"Status: {message}")

    def update_stats(self, passed: int, failed: int, skipped: int, errors: int) -> None:
        """Update test count labels."""
        logger.debug(
            f"TestExecutionProgressView: Updating stats. Passed: {passed}, Failed: {failed}, Skipped: {skipped}, Errors: {errors}."
        )
        self.passed_label.setText(f"Passed: {passed}")
        self.failed_label.setText(f"Failed: {failed}")
        self.skipped_label.setText(f"Skipped: {skipped}")
        self.errors_label.setText(f"Errors: {errors}")

    def _update_elapsed_time(self) -> None:
        """Update the elapsed time display."""
        self._elapsed_seconds += 1
        minutes = self._elapsed_seconds // 60
        seconds = self._elapsed_seconds % 60
        # This logs every second, might be too verbose. Consider logging less frequently or removing.
        # logger.debug(f"TestExecutionProgressView: Updating elapsed time. Elapsed: {minutes:02d}:{seconds:02d}.")
        self.elapsed_time_label.setText(f"Elapsed: {minutes:02d}:{seconds:02d}")

    def start_timer(self) -> None:
        """Start the elapsed time timer."""
        logger.debug("TestExecutionProgressView: Starting timer.")
        self._elapsed_seconds = 0
        self._update_elapsed_time()  # Show 00:00 immediately
        self._timer.start(1000)  # Update every second
        self.cancel_button.setEnabled(True)
        logger.debug("TestExecutionProgressView: Timer started, cancel button enabled.")

    def stop_timer(self) -> None:
        """Stop the elapsed time timer."""
        logger.debug("TestExecutionProgressView: Stopping timer.")
        self._timer.stop()
        self.cancel_button.setEnabled(False)
        logger.debug("TestExecutionProgressView: Timer stopped, cancel button disabled.")

    def reset_view(self) -> None:
        """Reset the view to its initial state."""
        logger.debug("TestExecutionProgressView: Resetting view.")
        self.update_progress(0, "Idle")
        self.update_stats(0, 0, 0, 0)
        self.elapsed_time_label.setText("Elapsed: 00:00")
        self.remaining_time_label.setText("Remaining: N/A")
        self._elapsed_seconds = 0
        if self._timer.isActive():
            logger.debug("TestExecutionProgressView: Stopping active timer during reset.")
            self._timer.stop()
        self.cancel_button.setEnabled(False)
        self.hide()
        logger.debug("TestExecutionProgressView: View reset and hidden.")

    def show_view(self, initial_message: str = "Initializing...") -> None:
        """Make the view visible and set an initial message."""
        logger.debug(
            f"TestExecutionProgressView: Showing view. Initial message: '{initial_message}'."
        )
        self.status_message_label.setText(f"Status: {initial_message}")
        self.show()
        logger.debug("TestExecutionProgressView: View shown.")
