"""
Base implementation of the state machine components.

This module provides concrete implementations of the state machine protocols
defined in the protocols module.
"""

import logging
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
)

from .errors import (
    DuplicateStateError,
    DuplicateTransitionError,
    InvalidStateError,
    NoInitialStateError,
)
from .protocols import State, Transition, TransitionResult

# Type variables
TContext = TypeVar("TContext")
TEvent = TypeVar("TEvent")

logger = logging.getLogger(__name__)


class BaseState(Generic[TContext]):
    """
    Base implementation of the State protocol.

    This class provides a simple implementation of the State protocol
    with customizable enter and exit actions.
    """

    def __init__(
        self,
        name: str,
        on_enter_action: Optional[Callable[[TContext], None]] = None,
        on_exit_action: Optional[Callable[[TContext], None]] = None,
    ):
        """
        Initialize a new state.

        Args:
            name: The name of the state
            on_enter_action: Optional action to execute when entering the state
            on_exit_action: Optional action to execute when exiting the state
        """
        self._name = name
        self._on_enter_action = on_enter_action
        self._on_exit_action = on_exit_action

    @property
    def name(self) -> str:
        """Get the name of the state."""
        return self._name

    def on_enter(self, context: TContext) -> None:
        """
        Execute the enter action if defined.

        Args:
            context: The state machine's context
        """
        logger.debug(f"Entering state: {self.name}")
        if self._on_enter_action:
            self._on_enter_action(context)

    def on_exit(self, context: TContext) -> None:
        """
        Execute the exit action if defined.

        Args:
            context: The state machine's context
        """
        logger.debug(f"Exiting state: {self.name}")
        if self._on_exit_action:
            self._on_exit_action(context)


class BaseTransition(Generic[TContext, TEvent]):
    """
    Base implementation of the Transition protocol.

    This class provides a simple implementation of the Transition protocol
    with customizable guard condition and action.
    """

    def __init__(
        self,
        source_state: str,
        target_state: str,
        trigger: str,
        guard: Optional[Callable[[TContext, Optional[TEvent]], bool]] = None,
        action: Optional[Callable[[TContext, Optional[TEvent]], None]] = None,
    ):
        """
        Initialize a new transition.

        Args:
            source_state: The name of the source state
            target_state: The name of the target state
            trigger: The name of the event that triggers this transition
            guard: Optional function that determines if the transition can occur
            action: Optional action to execute during the transition
        """
        self._source_state = source_state
        self._target_state = target_state
        self._trigger = trigger
        self._guard = guard
        self._action = action

    @property
    def source_state(self) -> str:
        """Get the name of the source state."""
        return self._source_state

    @property
    def target_state(self) -> str:
        """Get the name of the target state."""
        return self._target_state

    @property
    def trigger(self) -> str:
        """Get the name of the event that triggers this transition."""
        return self._trigger

    def can_transit(self, context: TContext, event: Optional[TEvent] = None) -> bool:
        """
        Determine if the transition can occur.

        Args:
            context: The state machine's context
            event: Optional event data

        Returns:
            True if the guard condition is satisfied (or no guard is defined),
            False otherwise
        """
        if self._guard:
            try:
                return self._guard(context, event)
            except Exception as e:
                logger.error(f"Error in guard condition: {e}")
                return False
        return True

    def execute(self, context: TContext, event: Optional[TEvent] = None) -> None:
        """
        Execute the transition action if defined.

        Args:
            context: The state machine's context
            event: Optional event data
        """
        logger.debug(
            f"Executing transition from '{self.source_state}' to '{self.target_state}'"
        )
        if self._action:
            self._action(context, event)


class BaseStateMachine(Generic[TContext, TEvent]):
    """
    Base implementation of the StateMachine protocol.

    This class provides a complete implementation of the StateMachine protocol
    with state and transition management, event handling, and error handling.
    """

    def __init__(self, context: TContext):
        """
        Initialize a new state machine.

        Args:
            context: The context for the state machine
        """
        self._context = context
        self._states: Dict[str, State[TContext]] = {}
        self._transitions: Dict[str, Dict[str, Transition[TContext, TEvent]]] = {}
        self._initial_state: Optional[str] = None
        self._current_state: Optional[State[TContext]] = None
        self._history: List[str] = []
        self._listeners: Dict[str, List[Callable[..., None]]] = {}

    @property
    def current_state(self) -> State[TContext]:
        """Get the current state of the state machine."""
        if not self._current_state:
            raise NoInitialStateError()
        return self._current_state

    @property
    def current_state_name(self) -> str:
        """Get the name of the current state."""
        return self.current_state.name

    @property
    def states(self) -> Dict[str, State[TContext]]:
        """Get all states registered with the state machine."""
        return self._states.copy()

    @property
    def context(self) -> TContext:
        """Get the context of the state machine."""
        return self._context

    @property
    def history(self) -> List[str]:
        """Get the history of visited states."""
        return self._history.copy()

    def add_state(self, state: State[TContext], is_initial: bool = False) -> None:
        """
        Add a state to the state machine.

        Args:
            state: The state to add
            is_initial: Whether this is the initial state

        Raises:
            DuplicateStateError: If a state with the same name already exists
        """
        if state.name in self._states:
            raise DuplicateStateError(state.name)

        self._states[state.name] = state

        # Initialize transitions dictionary for this state
        if state.name not in self._transitions:
            self._transitions[state.name] = {}

        if is_initial or self._initial_state is None:
            self._initial_state = state.name

            # If we don't have a current state yet, set it to the initial state
            if self._current_state is None:
                self._current_state = state
                self._history.append(state.name)
                state.on_enter(self._context)

    def add_transition(self, transition: Transition[TContext, TEvent]) -> None:
        """
        Add a transition to the state machine.

        Args:
            transition: The transition to add

        Raises:
            InvalidStateError: If the source or target state doesn't exist
            DuplicateTransitionError: If a transition with the same source and trigger already exists
        """
        # Verify that source and target states exist
        if transition.source_state not in self._states:
            raise InvalidStateError(transition.source_state)

        if transition.target_state not in self._states:
            raise InvalidStateError(transition.target_state)

        # Initialize transitions dictionary for the source state if needed
        if transition.source_state not in self._transitions:
            self._transitions[transition.source_state] = {}

        # Check for duplicate transition
        if transition.trigger in self._transitions[transition.source_state]:
            raise DuplicateTransitionError(transition.source_state, transition.trigger)

        # Add the transition
        self._transitions[transition.source_state][transition.trigger] = transition

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

        Raises:
            NoInitialStateError: If no initial state has been set
        """
        if not self._current_state:
            raise NoInitialStateError()

        current_state_name = self._current_state.name

        # Get transitions from the current state
        state_transitions = self._transitions.get(current_state_name, {})

        # Check if the trigger exists for the current state
        if trigger_name not in state_transitions:
            self._fire_event("invalid_transition", current_state_name, trigger_name)
            return TransitionResult.INVALID_TRANSITION

        # Get the transition
        transition = state_transitions[trigger_name]

        # Check the guard condition
        if not transition.can_transit(self._context, event):
            self._fire_event("guard_failed", current_state_name, trigger_name)
            return TransitionResult.FAILED_GUARD_CONDITION

        # Get the target state
        target_state_name = transition.target_state
        if target_state_name not in self._states:
            self._fire_event("invalid_state", target_state_name)
            return TransitionResult.INVALID_STATE

        target_state = self._states[target_state_name]

        try:
            # Execute the transition
            self._fire_event(
                "transition_start", current_state_name, target_state_name, trigger_name
            )

            # Exit the current state
            self._current_state.on_exit(self._context)

            # Execute the transition action
            transition.execute(self._context, event)

            # Enter the new state
            self._current_state = target_state
            self._history.append(target_state_name)
            target_state.on_enter(self._context)

            self._fire_event(
                "transition_complete",
                current_state_name,
                target_state_name,
                trigger_name,
            )
            return TransitionResult.SUCCESS

        except Exception as e:
            self._fire_event(
                "transition_error",
                current_state_name,
                target_state_name,
                trigger_name,
                e,
            )
            logger.error(
                f"Error during transition from '{current_state_name}' to '{target_state_name}': {e}"
            )
            # Re-enter the original state to maintain consistency
            self._current_state.on_enter(self._context)
            return TransitionResult.FAILED_ACTION

    def can_trigger(self, trigger_name: str) -> bool:
        """
        Check if a trigger can be fired from the current state.

        Args:
            trigger_name: The name of the trigger

        Returns:
            True if the trigger exists for the current state, False otherwise
        """
        if not self._current_state:
            return False

        current_state_name = self._current_state.name
        state_transitions = self._transitions.get(current_state_name, {})

        return trigger_name in state_transitions

    def get_permitted_triggers(self) -> Set[str]:
        """
        Get all triggers that can be fired from the current state.

        Returns:
            Set of trigger names that can be fired from the current state
        """
        if not self._current_state:
            return set()

        current_state_name = self._current_state.name
        state_transitions = self._transitions.get(current_state_name, {})

        return set(state_transitions.keys())

    def reset(self) -> None:
        """
        Reset the state machine to its initial state.

        Raises:
            NoInitialStateError: If no initial state has been set
        """
        if not self._initial_state:
            raise NoInitialStateError()

        # Exit the current state if it exists
        if self._current_state:
            self._current_state.on_exit(self._context)

        # Set the current state to the initial state
        self._current_state = self._states[self._initial_state]
        self._history = [self._initial_state]

        # Enter the initial state
        self._current_state.on_enter(self._context)

        self._fire_event("reset", self._initial_state)

    def add_event_listener(
        self, event_name: str, callback: Callable[..., None]
    ) -> None:
        """
        Add an event listener for state machine events.

        Args:
            event_name: The name of the event to listen for
            callback: The function to call when the event occurs
        """
        if event_name not in self._listeners:
            self._listeners[event_name] = []

        self._listeners[event_name].append(callback)

    def remove_event_listener(
        self, event_name: str, callback: Callable[..., None]
    ) -> None:
        """
        Remove an event listener.

        Args:
            event_name: The name of the event
            callback: The callback function to remove
        """
        if event_name in self._listeners:
            self._listeners[event_name] = [
                listener
                for listener in self._listeners[event_name]
                if listener != callback
            ]

    def _fire_event(self, event_name: str, *args) -> None:
        """
        Fire an event to all registered listeners.

        Args:
            event_name: The name of the event
            *args: Arguments to pass to the listeners
        """
        if event_name in self._listeners:
            for listener in self._listeners[event_name]:
                try:
                    listener(*args)
                except Exception as e:
                    logger.error(f"Error in event listener for '{event_name}': {e}")


def create_state(
    name: str,
    on_enter_action: Optional[Callable[[Any], None]] = None,
    on_exit_action: Optional[Callable[[Any], None]] = None,
) -> BaseState:
    """
    Create a new BaseState instance.

    This is a convenience function for creating states without needing
    to directly use the BaseState class.

    Args:
        name: The name of the state
        on_enter_action: Optional action to execute when entering the state
        on_exit_action: Optional action to execute when exiting the state

    Returns:
        A new BaseState instance
    """
    return BaseState(name, on_enter_action, on_exit_action)


def create_transition(
    source_state: str,
    target_state: str,
    trigger: str,
    guard: Optional[Callable[[Any, Optional[Any]], bool]] = None,
    action: Optional[Callable[[Any, Optional[Any]], None]] = None,
) -> BaseTransition:
    """
    Create a new BaseTransition instance.

    This is a convenience function for creating transitions without needing
    to directly use the BaseTransition class.

    Args:
        source_state: The name of the source state
        target_state: The name of the target state
        trigger: The name of the event that triggers this transition
        guard: Optional function that determines if the transition can occur
        action: Optional action to execute during the transition

    Returns:
        A new BaseTransition instance
    """
    return BaseTransition(source_state, target_state, trigger, guard, action)
