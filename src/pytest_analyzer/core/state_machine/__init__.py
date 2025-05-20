"""
State Machine package for pytest_analyzer.

This package provides a flexible state machine implementation
for modeling complex processes and workflows.
"""

from .base import (
    BaseState,
    BaseStateMachine,
    BaseTransition,
    create_state,
    create_transition,
)
from .errors import (
    DuplicateStateError,
    DuplicateTransitionError,
    InvalidStateError,
    InvalidTransitionError,
    NoInitialStateError,
    StateError,
    StateMachineError,
    TransitionActionError,
    TransitionError,
)
from .protocols import State, StateMachine, Transition, TransitionResult

__all__ = [
    # Protocols
    "State",
    "StateMachine",
    "Transition",
    "TransitionResult",
    # Base implementations
    "BaseState",
    "BaseStateMachine",
    "BaseTransition",
    "create_state",
    "create_transition",
    # Errors
    "StateMachineError",
    "StateError",
    "TransitionError",
    "InvalidStateError",
    "InvalidTransitionError",
    "DuplicateStateError",
    "DuplicateTransitionError",
    "NoInitialStateError",
    "TransitionActionError",
]
