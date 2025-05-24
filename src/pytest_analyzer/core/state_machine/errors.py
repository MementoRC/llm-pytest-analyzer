"""
Error classes for the state machine module.
"""

from ..errors import PytestAnalyzerError


class StateMachineError(PytestAnalyzerError):
    """Base class for state machine errors."""

    def __init__(self, message: str = None, *args):
        self.message = message or "An error occurred in the state machine"
        super().__init__(self.message, *args)


class StateError(StateMachineError):
    """Error related to state operations."""

    def __init__(self, message: str = None, *args):
        self.message = message or "Error in state operation"
        super().__init__(self.message, *args)


class TransitionError(StateMachineError):
    """Error related to transition operations."""

    def __init__(self, message: str = None, *args):
        self.message = message or "Error in transition operation"
        super().__init__(self.message, *args)


class InvalidStateError(StateError):
    """Error when an invalid state is referenced."""

    def __init__(self, state_name: str, *args):
        self.message = f"Invalid state: {state_name}"
        super().__init__(self.message, *args)


class InvalidTransitionError(TransitionError):
    """Error when an invalid transition is attempted."""

    def __init__(self, current_state: str, trigger: str, *args):
        self.message = f"No transition defined from state '{current_state}' for trigger '{trigger}'"
        super().__init__(self.message, *args)


class DuplicateStateError(StateError):
    """Error when a duplicate state is added."""

    def __init__(self, state_name: str, *args):
        self.message = f"State with name '{state_name}' already exists"
        super().__init__(self.message, *args)


class DuplicateTransitionError(TransitionError):
    """Error when a duplicate transition is added."""

    def __init__(self, source: str, trigger: str, *args):
        self.message = f"Transition from state '{source}' with trigger '{trigger}' already exists"
        super().__init__(self.message, *args)


class NoInitialStateError(StateError):
    """Error when no initial state is defined."""

    def __init__(self, *args):
        self.message = "No initial state defined for the state machine"
        super().__init__(self.message, *args)


class TransitionActionError(TransitionError):
    """Error during execution of a transition action."""

    def __init__(self, source: str, target: str, trigger: str, cause: Exception = None, *args):
        self.message = f"Error executing action for transition from '{source}' to '{target}' with trigger '{trigger}'"
        if cause:
            self.message += f": {str(cause)}"
        super().__init__(self.message, *args)
        self.cause = cause
