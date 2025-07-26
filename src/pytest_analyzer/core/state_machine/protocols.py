"""
Protocol interfaces for the state machine.

This module defines the core interfaces for the state machine components,
establishing contracts that implementations must follow.
"""

from enum import Enum, auto
from typing import (
    Dict,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

# Type variables for generic types
TState = TypeVar("TState", bound="State")
TContext = TypeVar("TContext")
TEvent = TypeVar("TEvent")
TStateMachine = TypeVar("TStateMachine", bound="StateMachine")


class TransitionResult(Enum):
    """Result of a state transition attempt."""

    SUCCESS = auto()
    """Transition completed successfully."""

    FAILED_GUARD_CONDITION = auto()
    """Transition failed because guard condition wasn't met."""

    FAILED_VALIDATION = auto()
    """Transition failed validation."""

    FAILED_ACTION = auto()
    """Transition action failed during execution."""

    INVALID_TRANSITION = auto()
    """Transition is not defined for the current state."""

    INVALID_STATE = auto()
    """The target state doesn't exist in the state machine."""


@runtime_checkable
class State(Protocol[TContext]):  # type: ignore[misc]
    """Protocol for a state in the state machine."""

    @property
    def name(self) -> str:
        """Get the name of the state."""
        ...

    def on_enter(self, context: TContext) -> None:
        """
        Called when entering the state.

        Args:
            context: The state machine's context
        """
        ...

    def on_exit(self, context: TContext) -> None:
        """
        Called when exiting the state.

        Args:
            context: The state machine's context
        """
        ...


@runtime_checkable
class Transition(Protocol[TContext, TEvent]):  # type: ignore[misc]
    """Protocol for a transition between states."""

    @property
    def source_state(self) -> str:
        """Get the name of the source state."""
        ...

    @property
    def target_state(self) -> str:
        """Get the name of the target state."""
        ...

    @property
    def trigger(self) -> str:
        """Get the name of the event that triggers this transition."""
        ...

    def can_transit(self, context: TContext, event: TEvent) -> bool:
        """
        Determine if the transition can occur.

        This is the guard condition that must be satisfied for the transition to proceed.

        Args:
            context: The state machine's context
            event: The event data

        Returns:
            True if the transition can proceed, False otherwise
        """
        ...

    def execute(self, context: TContext, event: TEvent) -> None:
        """
        Execute the transition action.

        Args:
            context: The state machine's context
            event: The event data
        """
        ...


@runtime_checkable
class StateMachine(Protocol[TContext, TEvent]):  # type: ignore[misc]
    """Protocol for a state machine."""

    @property
    def current_state(self) -> State[TContext]:
        """Get the current state of the state machine."""
        ...

    @property
    def states(self) -> Dict[str, State[TContext]]:
        """Get all states registered with the state machine."""
        ...

    @property
    def context(self) -> TContext:
        """Get the context of the state machine."""
        ...

    def add_state(self, state: State[TContext], is_initial: bool = False) -> None:
        """
        Add a state to the state machine.

        Args:
            state: The state to add
            is_initial: Whether this is the initial state
        """
        ...

    def add_transition(self, transition: Transition[TContext, TEvent]) -> None:
        """
        Add a transition to the state machine.

        Args:
            transition: The transition to add
        """
        ...

    def trigger(
        self, trigger_name: str, event: Optional[TEvent] = None
    ) -> TransitionResult:
        """
        Trigger a transition by name.

        Args:
            trigger_name: The name of the trigger
            event: Optional event data

        Returns:
            Result of the transition attempt
        """
        ...

    def can_trigger(self, trigger_name: str) -> bool:
        """
        Check if a trigger can be fired from the current state.

        Args:
            trigger_name: The name of the trigger

        Returns:
            True if the trigger can be fired, False otherwise
        """
        ...

    def reset(self) -> None:
        """
        Reset the state machine to its initial state.
        """
        ...
