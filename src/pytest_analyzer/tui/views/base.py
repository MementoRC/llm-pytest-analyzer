from textual.widget import Widget


class BaseView(Widget):
    """
    Abstract base class for TUI views/widgets.

    This class can be used to provide common functionality or styling
    to all custom views within the TUI application.
    """

    def __init__(
        self,
        *children,
        name: str | None = None,
        widget_id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(*children, name=name, id=widget_id, classes=classes, disabled=disabled)
        self.app_instance = self.app  # Convenience accessor for the TUIApp instance
