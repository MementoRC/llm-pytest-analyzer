"""
Tests for the base state machine implementation.
"""

from unittest.mock import MagicMock

import pytest

from src.pytest_analyzer.core.state_machine import (
    BaseState,
    BaseStateMachine,
    BaseTransition,
    DuplicateStateError,
    DuplicateTransitionError,
    InvalidStateError,
    NoInitialStateError,
    TransitionResult,
    create_state,
    create_transition,
)


class TestBaseState:
    """Tests for the BaseState class."""

    def test_base_state_properties(self):
        """Test the basic properties of BaseState."""
        # Arrange
        state_name = "test_state"
        on_enter = MagicMock()
        on_exit = MagicMock()

        # Act
        state = BaseState(state_name, on_enter, on_exit)

        # Assert
        assert state.name == state_name

    def test_on_enter_calls_action(self):
        """Test that on_enter calls the provided action."""
        # Arrange
        on_enter = MagicMock()
        state = BaseState("test_state", on_enter)
        context = {"value": 42}

        # Act
        state.on_enter(context)

        # Assert
        on_enter.assert_called_once_with(context)

    def test_on_exit_calls_action(self):
        """Test that on_exit calls the provided action."""
        # Arrange
        on_exit = MagicMock()
        state = BaseState("test_state", None, on_exit)
        context = {"value": 42}

        # Act
        state.on_exit(context)

        # Assert
        on_exit.assert_called_once_with(context)

    def test_on_enter_without_action(self):
        """Test that on_enter works when no action is provided."""
        # Arrange
        state = BaseState("test_state")
        context = {"value": 42}

        # Act & Assert (no exception should be raised)
        state.on_enter(context)

    def test_on_exit_without_action(self):
        """Test that on_exit works when no action is provided."""
        # Arrange
        state = BaseState("test_state")
        context = {"value": 42}

        # Act & Assert (no exception should be raised)
        state.on_exit(context)


class TestBaseTransition:
    """Tests for the BaseTransition class."""

    def test_base_transition_properties(self):
        """Test the basic properties of BaseTransition."""
        # Arrange
        source = "source_state"
        target = "target_state"
        trigger = "test_trigger"
        guard = MagicMock(return_value=True)
        action = MagicMock()

        # Act
        transition = BaseTransition(source, target, trigger, guard, action)

        # Assert
        assert transition.source_state == source
        assert transition.target_state == target
        assert transition.trigger == trigger

    def test_can_transit_with_guard(self):
        """Test that can_transit calls the guard function."""
        # Arrange
        guard = MagicMock(return_value=True)
        transition = BaseTransition("source", "target", "trigger", guard)
        context = {"value": 42}
        event = {"data": "test"}

        # Act
        result = transition.can_transit(context, event)

        # Assert
        assert result is True
        guard.assert_called_once_with(context, event)

    def test_can_transit_without_guard(self):
        """Test that can_transit returns True when no guard is provided."""
        # Arrange
        transition = BaseTransition("source", "target", "trigger")
        context = {"value": 42}

        # Act
        result = transition.can_transit(context)

        # Assert
        assert result is True

    def test_can_transit_with_failing_guard(self):
        """Test that can_transit returns False when guard returns False."""
        # Arrange
        guard = MagicMock(return_value=False)
        transition = BaseTransition("source", "target", "trigger", guard)
        context = {"value": 42}

        # Act
        result = transition.can_transit(context)

        # Assert
        assert result is False

    def test_can_transit_with_exception_in_guard(self):
        """Test that can_transit returns False when guard raises an exception."""
        # Arrange
        guard = MagicMock(side_effect=Exception("Test exception"))
        transition = BaseTransition("source", "target", "trigger", guard)
        context = {"value": 42}

        # Act
        result = transition.can_transit(context)

        # Assert
        assert result is False

    def test_execute_calls_action(self):
        """Test that execute calls the action function."""
        # Arrange
        action = MagicMock()
        transition = BaseTransition("source", "target", "trigger", None, action)
        context = {"value": 42}
        event = {"data": "test"}

        # Act
        transition.execute(context, event)

        # Assert
        action.assert_called_once_with(context, event)

    def test_execute_without_action(self):
        """Test that execute works when no action is provided."""
        # Arrange
        transition = BaseTransition("source", "target", "trigger")
        context = {"value": 42}

        # Act & Assert (no exception should be raised)
        transition.execute(context)


class TestBaseStateMachine:
    """Tests for the BaseStateMachine class."""

    def test_initial_state(self):
        """Test that initial state is set correctly."""
        # Arrange
        context = {"value": 42}
        state_machine = BaseStateMachine(context)
        state = create_state("initial_state")

        # Act
        state_machine.add_state(state, is_initial=True)

        # Assert
        assert state_machine.current_state == state
        assert state_machine.current_state_name == "initial_state"
        assert state_machine.context == context

    def test_add_duplicate_state(self):
        """Test that adding a duplicate state raises an error."""
        # Arrange
        state_machine = BaseStateMachine({})
        state1 = create_state("test_state")
        state2 = create_state("test_state")

        # Act & Assert
        state_machine.add_state(state1)
        with pytest.raises(DuplicateStateError):
            state_machine.add_state(state2)

    def test_add_transition(self):
        """Test adding a transition."""
        # Arrange
        state_machine = BaseStateMachine({})
        state1 = create_state("state1")
        state2 = create_state("state2")
        state_machine.add_state(state1, is_initial=True)
        state_machine.add_state(state2)

        # Act
        transition = create_transition("state1", "state2", "go")
        state_machine.add_transition(transition)

        # Assert
        assert state_machine.can_trigger("go")

    def test_add_transition_invalid_source(self):
        """Test adding a transition with invalid source state."""
        # Arrange
        state_machine = BaseStateMachine({})
        state = create_state("state")
        state_machine.add_state(state, is_initial=True)

        # Act & Assert
        transition = create_transition("invalid", "state", "go")
        with pytest.raises(InvalidStateError):
            state_machine.add_transition(transition)

    def test_add_transition_invalid_target(self):
        """Test adding a transition with invalid target state."""
        # Arrange
        state_machine = BaseStateMachine({})
        state = create_state("state")
        state_machine.add_state(state, is_initial=True)

        # Act & Assert
        transition = create_transition("state", "invalid", "go")
        with pytest.raises(InvalidStateError):
            state_machine.add_transition(transition)

    def test_add_duplicate_transition(self):
        """Test adding a duplicate transition."""
        # Arrange
        state_machine = BaseStateMachine({})
        state1 = create_state("state1")
        state2 = create_state("state2")
        state_machine.add_state(state1, is_initial=True)
        state_machine.add_state(state2)

        # Act & Assert
        transition1 = create_transition("state1", "state2", "go")
        transition2 = create_transition("state1", "state2", "go")
        state_machine.add_transition(transition1)
        with pytest.raises(DuplicateTransitionError):
            state_machine.add_transition(transition2)

    def test_trigger_successful_transition(self):
        """Test triggering a successful transition."""
        # Arrange
        context = {}
        state_machine = BaseStateMachine(context)
        state1 = create_state("state1")
        state2 = create_state("state2")
        state_machine.add_state(state1, is_initial=True)
        state_machine.add_state(state2)

        # Track state enter/exit calls
        state1_exit = MagicMock()
        state2_enter = MagicMock()
        state1._on_exit_action = state1_exit
        state2._on_enter_action = state2_enter

        # Create a transition with an action
        action = MagicMock()
        transition = create_transition("state1", "state2", "go", action=action)
        state_machine.add_transition(transition)

        # Act
        result = state_machine.trigger("go")

        # Assert
        assert result == TransitionResult.SUCCESS
        assert state_machine.current_state_name == "state2"
        state1_exit.assert_called_once_with(context)
        state2_enter.assert_called_once_with(context)
        action.assert_called_once()

    def test_trigger_with_guard_condition(self):
        """Test triggering a transition with a guard condition."""
        # Arrange
        context = {"allowed": False}
        state_machine = BaseStateMachine(context)
        state1 = create_state("state1")
        state2 = create_state("state2")
        state_machine.add_state(state1, is_initial=True)
        state_machine.add_state(state2)

        # Create a transition with a guard that depends on context
        def guard(ctx, _):
            return ctx["allowed"]

        transition = create_transition("state1", "state2", "go", guard=guard)
        state_machine.add_transition(transition)

        # Act - Should fail due to guard
        result1 = state_machine.trigger("go")

        # Modify context to allow transition
        context["allowed"] = True

        # Act - Should succeed now
        result2 = state_machine.trigger("go")

        # Assert
        assert result1 == TransitionResult.FAILED_GUARD_CONDITION
        assert result2 == TransitionResult.SUCCESS
        assert state_machine.current_state_name == "state2"

    def test_trigger_invalid_transition(self):
        """Test triggering an invalid transition."""
        # Arrange
        state_machine = BaseStateMachine({})
        state = create_state("state")
        state_machine.add_state(state, is_initial=True)

        # Act
        result = state_machine.trigger("invalid")

        # Assert
        assert result == TransitionResult.INVALID_TRANSITION
        assert state_machine.current_state_name == "state"

    def test_get_permitted_triggers(self):
        """Test getting permitted triggers."""
        # Arrange
        state_machine = BaseStateMachine({})
        state1 = create_state("state1")
        state2 = create_state("state2")
        state_machine.add_state(state1, is_initial=True)
        state_machine.add_state(state2)

        transition1 = create_transition("state1", "state2", "go1")
        transition2 = create_transition("state1", "state2", "go2")
        state_machine.add_transition(transition1)
        state_machine.add_transition(transition2)

        # Act
        permitted = state_machine.get_permitted_triggers()

        # Assert
        assert permitted == {"go1", "go2"}

    def test_reset(self):
        """Test resetting the state machine."""
        # Arrange
        context = {}
        state_machine = BaseStateMachine(context)
        state1 = create_state("state1")
        state2 = create_state("state2")
        state_machine.add_state(state1, is_initial=True)
        state_machine.add_state(state2)

        # Track state enter/exit calls
        state1_enter = MagicMock()
        state1_exit = MagicMock()
        state2_enter = MagicMock()
        state2_exit = MagicMock()
        state1._on_enter_action = state1_enter
        state1._on_exit_action = state1_exit
        state2._on_enter_action = state2_enter
        state2._on_exit_action = state2_exit

        transition = create_transition("state1", "state2", "go")
        state_machine.add_transition(transition)

        # Move to state2
        state_machine.trigger("go")
        assert state_machine.current_state_name == "state2"

        # Reset call counts
        state1_enter.reset_mock()
        state1_exit.reset_mock()
        state2_enter.reset_mock()
        state2_exit.reset_mock()

        # Act
        state_machine.reset()

        # Assert
        assert state_machine.current_state_name == "state1"
        state2_exit.assert_called_once_with(context)
        state1_enter.assert_called_once_with(context)

    def test_reset_without_initial_state(self):
        """Test resetting without an initial state."""
        # Arrange
        state_machine = BaseStateMachine({})

        # Act & Assert
        with pytest.raises(NoInitialStateError):
            state_machine.reset()

    def test_state_history(self):
        """Test that state history is maintained."""
        # Arrange
        state_machine = BaseStateMachine({})
        state1 = create_state("state1")
        state2 = create_state("state2")
        state3 = create_state("state3")
        state_machine.add_state(state1, is_initial=True)
        state_machine.add_state(state2)
        state_machine.add_state(state3)

        transition1 = create_transition("state1", "state2", "go1")
        transition2 = create_transition("state2", "state3", "go2")
        state_machine.add_transition(transition1)
        state_machine.add_transition(transition2)

        # Act
        state_machine.trigger("go1")
        state_machine.trigger("go2")

        # Assert
        assert state_machine.history == ["state1", "state2", "state3"]

    def test_event_listeners(self):
        """Test event listener system."""
        # Arrange
        state_machine = BaseStateMachine({})
        state1 = create_state("state1")
        state2 = create_state("state2")
        state_machine.add_state(state1, is_initial=True)
        state_machine.add_state(state2)

        transition = create_transition("state1", "state2", "go")
        state_machine.add_transition(transition)

        # Set up event listeners
        transition_start = MagicMock()
        transition_complete = MagicMock()
        state_machine.add_event_listener("transition_start", transition_start)
        state_machine.add_event_listener("transition_complete", transition_complete)

        # Act
        state_machine.trigger("go")

        # Assert
        transition_start.assert_called_once_with("state1", "state2", "go")
        transition_complete.assert_called_once_with("state1", "state2", "go")

    def test_remove_event_listener(self):
        """Test removing an event listener."""
        # Arrange
        state_machine = BaseStateMachine({})
        state1 = create_state("state1")
        state2 = create_state("state2")
        state_machine.add_state(state1, is_initial=True)
        state_machine.add_state(state2)

        transition = create_transition("state1", "state2", "go")
        state_machine.add_transition(transition)

        # Set up event listener
        transition_start = MagicMock()
        state_machine.add_event_listener("transition_start", transition_start)

        # Remove the listener
        state_machine.remove_event_listener("transition_start", transition_start)

        # Act
        state_machine.trigger("go")

        # Assert
        transition_start.assert_not_called()

    def test_complex_workflow(self):
        """Test a more complex workflow with multiple states and transitions."""
        # Arrange - Create a simple workflow for a document approval process
        context = {"document": {"status": "draft", "approvals": 0}}
        state_machine = BaseStateMachine(context)

        # Create states
        draft = create_state("draft")
        review = create_state("review")
        approved = create_state("approved")
        rejected = create_state("rejected")

        # Add states to machine
        state_machine.add_state(draft, is_initial=True)
        state_machine.add_state(review)
        state_machine.add_state(approved)
        state_machine.add_state(rejected)

        # Define actions
        def submit_action(ctx, _):
            ctx["document"]["status"] = "in_review"

        def approve_action(ctx, _):
            ctx["document"]["approvals"] += 1
            ctx["document"]["status"] = "approved"

        def reject_action(ctx, _):
            ctx["document"]["status"] = "rejected"

        def resubmit_action(ctx, _):
            ctx["document"]["status"] = "in_review"

        # Create transitions
        submit = create_transition("draft", "review", "submit", action=submit_action)
        approve = create_transition(
            "review", "approved", "approve", action=approve_action
        )
        reject = create_transition("review", "rejected", "reject", action=reject_action)
        resubmit = create_transition(
            "rejected", "review", "resubmit", action=resubmit_action
        )

        # Add transitions to machine
        state_machine.add_transition(submit)
        state_machine.add_transition(approve)
        state_machine.add_transition(reject)
        state_machine.add_transition(resubmit)

        # Act - Run through the workflow
        assert state_machine.current_state_name == "draft"

        # Submit the document
        result1 = state_machine.trigger("submit")
        assert result1 == TransitionResult.SUCCESS
        assert state_machine.current_state_name == "review"
        assert context["document"]["status"] == "in_review"

        # Reject the document
        result2 = state_machine.trigger("reject")
        assert result2 == TransitionResult.SUCCESS
        assert state_machine.current_state_name == "rejected"
        assert context["document"]["status"] == "rejected"

        # Resubmit the document
        result3 = state_machine.trigger("resubmit")
        assert result3 == TransitionResult.SUCCESS
        assert state_machine.current_state_name == "review"
        assert context["document"]["status"] == "in_review"

        # Approve the document
        result4 = state_machine.trigger("approve")
        assert result4 == TransitionResult.SUCCESS
        assert state_machine.current_state_name == "approved"
        assert context["document"]["status"] == "approved"
        assert context["document"]["approvals"] == 1

        # Try an invalid transition (can't submit an already approved document)
        result5 = state_machine.trigger("submit")
        assert result5 == TransitionResult.INVALID_TRANSITION
        assert state_machine.current_state_name == "approved"  # State doesn't change

        # Verify history
        expected_history = ["draft", "review", "rejected", "review", "approved"]
        assert state_machine.history == expected_history
