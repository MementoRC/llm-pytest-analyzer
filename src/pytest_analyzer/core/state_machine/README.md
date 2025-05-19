# State Machine Framework

This module provides a flexible state machine implementation for modeling complex workflows and processes in the pytest-analyzer project.

## Table of Contents

- [Overview](#overview)
- [Key Components](#key-components)
- [Basic Usage](#basic-usage)
- [Advanced Features](#advanced-features)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)

## Overview

A state machine is a computational model that organizes behavior into a set of states, transitions between states, and actions that occur during those transitions. This implementation provides:

- A clean, type-safe API for defining states and transitions
- Support for context data that states and transitions can access and modify
- Guard conditions that determine whether transitions can occur
- Actions that execute during state entry, exit, and transitions
- Event system for monitoring state machine behavior
- Comprehensive error handling

## Key Components

The state machine framework consists of several key components:

### States

States represent the different stages of a process or workflow. Each state has:
- A unique name
- Optional enter and exit actions
- Access to the state machine's context

### Transitions

Transitions define how the state machine moves from one state to another. Each transition has:
- A source state
- A target state
- A trigger (event name)
- Optional guard condition
- Optional action to execute during the transition

### Events

The state machine fires events at key points in its operation, allowing external code to observe and respond to changes:
- `transition_start`: Fired when a transition begins
- `transition_complete`: Fired when a transition completes successfully
- `transition_error`: Fired when a transition encounters an error
- `invalid_transition`: Fired when an invalid transition is attempted
- `guard_failed`: Fired when a guard condition prevents a transition
- `invalid_state`: Fired when a transition targets an invalid state
- `reset`: Fired when the state machine is reset

## Basic Usage

### Creating a Simple State Machine

```python
from pytest_analyzer.core.state_machine import BaseStateMachine, create_state, create_transition

# Create a context object to store data
context = {"status": "new", "attempts": 0}

# Create a state machine
machine = BaseStateMachine(context)

# Define states
new_state = create_state("new")
processing_state = create_state("processing")
completed_state = create_state("completed")
failed_state = create_state("failed")

# Add states to machine (first one is initial)
machine.add_state(new_state, is_initial=True)
machine.add_state(processing_state)
machine.add_state(completed_state)
machine.add_state(failed_state)

# Define transitions
start = create_transition("new", "processing", "start")
complete = create_transition("processing", "completed", "complete")
fail = create_transition("processing", "failed", "fail")
retry = create_transition("failed", "processing", "retry")

# Add transitions to machine
machine.add_transition(start)
machine.add_transition(complete)
machine.add_transition(fail)
machine.add_transition(retry)

# Use the state machine
print(f"Current state: {machine.current_state_name}")  # "new"

# Trigger transitions
machine.trigger("start")
print(f"Current state: {machine.current_state_name}")  # "processing"

machine.trigger("complete")
print(f"Current state: {machine.current_state_name}")  # "completed"
```

### Using Actions and Guards

```python
from pytest_analyzer.core.state_machine import BaseStateMachine, create_state, create_transition

# Create context with data
context = {"document": {"status": "draft", "approvals": 0}}

# Create state machine
machine = BaseStateMachine(context)

# Define actions for states
def on_enter_review(ctx):
    print(f"Document entered review with status: {ctx['document']['status']}")

def on_exit_review(ctx):
    print(f"Document exited review with {ctx['document']['approvals']} approvals")

# Create states with enter/exit actions
draft = create_state("draft")
review = create_state("review", on_enter_review, on_exit_review)
approved = create_state("approved")
rejected = create_state("rejected")

# Add states
machine.add_state(draft, is_initial=True)
machine.add_state(review)
machine.add_state(approved)
machine.add_state(rejected)

# Define transition actions
def submit_action(ctx, _):
    ctx["document"]["status"] = "in_review"

def approve_action(ctx, _):
    ctx["document"]["approvals"] += 1
    ctx["document"]["status"] = "approved"

# Define a guard condition
def can_approve(ctx, _):
    # Document needs at least 2 approvals to move to approved state
    return ctx["document"]["approvals"] >= 2

# Create transitions with actions and guards
submit = create_transition("draft", "review", "submit", action=submit_action)
approve = create_transition("review", "approved", "approve",
                          guard=can_approve, action=approve_action)
reject = create_transition("review", "rejected", "reject")

# Add transitions
machine.add_transition(submit)
machine.add_transition(approve)
machine.add_transition(reject)

# Use the state machine
machine.trigger("submit")  # Moves to "review" state

# Try to approve, but guard condition will prevent it
machine.trigger("approve")  # Will return TransitionResult.FAILED_GUARD_CONDITION

# Update the context to satisfy the guard
context["document"]["approvals"] = 2

# Now the transition will succeed
machine.trigger("approve")  # Moves to "approved" state
```

## Advanced Features

### Event System

```python
from pytest_analyzer.core.state_machine import BaseStateMachine, create_state, create_transition

machine = BaseStateMachine({})

# Create and add states
s1 = create_state("state1")
s2 = create_state("state2")
machine.add_state(s1, is_initial=True)
machine.add_state(s2)

# Create and add transition
t = create_transition("state1", "state2", "go")
machine.add_transition(t)

# Define event listeners
def on_transition_start(from_state, to_state, trigger):
    print(f"Starting transition from {from_state} to {to_state} via {trigger}")

def on_transition_complete(from_state, to_state, trigger):
    print(f"Completed transition from {from_state} to {to_state} via {trigger}")

# Register event listeners
machine.add_event_listener("transition_start", on_transition_start)
machine.add_event_listener("transition_complete", on_transition_complete)

# Trigger the transition
machine.trigger("go")
# Will print:
# Starting transition from state1 to state2 via go
# Completed transition from state1 to state2 via go
```

### State History

```python
from pytest_analyzer.core.state_machine import BaseStateMachine, create_state, create_transition

# Create a workflow
machine = BaseStateMachine({})

# Add states and transitions
for state in ["start", "step1", "step2", "end"]:
    machine.add_state(create_state(state), is_initial=(state == "start"))

machine.add_transition(create_transition("start", "step1", "next"))
machine.add_transition(create_transition("step1", "step2", "next"))
machine.add_transition(create_transition("step2", "end", "next"))

# Execute the workflow
machine.trigger("next")
machine.trigger("next")
machine.trigger("next")

# Get the history
print(machine.history)  # ["start", "step1", "step2", "end"]
```

### Nested State Machines

You can create hierarchical state machines by embedding one state machine inside another:

```python
from pytest_analyzer.core.state_machine import BaseStateMachine, create_state, create_transition

# Create main context
main_context = {"status": "idle", "sub_machine": None}

# Create main state machine
main_machine = BaseStateMachine(main_context)

# Define a function to create and configure the sub state machine
def create_sub_machine():
    sub_context = {"step": 1}
    sub_machine = BaseStateMachine(sub_context)

    # Add states and transitions for sub machine
    sub_machine.add_state(create_state("sub_step1"), is_initial=True)
    sub_machine.add_state(create_state("sub_step2"))
    sub_machine.add_state(create_state("sub_complete"))

    sub_machine.add_transition(create_transition("sub_step1", "sub_step2", "next"))
    sub_machine.add_transition(create_transition("sub_step2", "sub_complete", "next"))

    return sub_machine

# Define main state actions
def on_enter_processing(ctx):
    # Create and store the sub machine when entering the processing state
    ctx["sub_machine"] = create_sub_machine()
    ctx["status"] = "processing"

def exit_processing(ctx):
    # Clean up the sub machine when exiting
    ctx["sub_machine"] = None

# Create main states
idle = create_state("idle")
processing = create_state("processing", on_enter_processing, exit_processing)
complete = create_state("complete")

# Add states to main machine
main_machine.add_state(idle, is_initial=True)
main_machine.add_state(processing)
main_machine.add_state(complete)

# Create a transition action that uses the sub machine
def process_step(ctx, _):
    sub_machine = ctx["sub_machine"]
    if sub_machine:
        # Execute one step in the sub machine
        sub_machine.trigger("next")

        # If the sub machine is complete, move to the complete state
        if sub_machine.current_state_name == "sub_complete":
            ctx["status"] = "ready_to_complete"
            return True
    return False

# Create transitions
start = create_transition("idle", "processing", "start")
process = create_transition("processing", "processing", "process", action=process_step)
finish = create_transition(
    "processing", "complete", "finish",
    guard=lambda ctx, _: ctx["status"] == "ready_to_complete"
)

# Add transitions
main_machine.add_transition(start)
main_machine.add_transition(process)
main_machine.add_transition(finish)

# Use the hierarchical state machine
main_machine.trigger("start")  # Creates and initializes the sub machine
main_machine.trigger("process")  # First step in sub machine
main_machine.trigger("process")  # Second step in sub machine (completes it)
main_machine.trigger("finish")  # Now we can finish
```

## Error Handling

The state machine provides robust error handling through specific exception types and error events.

### Error Types

- `StateMachineError`: Base error class for all state machine errors
- `StateError`: Errors related to state operations
  - `InvalidStateError`: When an invalid state is referenced
  - `DuplicateStateError`: When a duplicate state is added
  - `NoInitialStateError`: When no initial state is defined
- `TransitionError`: Errors related to transition operations
  - `InvalidTransitionError`: When an invalid transition is attempted
  - `DuplicateTransitionError`: When a duplicate transition is added
  - `TransitionActionError`: When a transition action fails

### Handling Transition Errors

```python
from pytest_analyzer.core.state_machine import (
    BaseStateMachine, create_state, create_transition, TransitionResult
)

# Create a state machine
machine = BaseStateMachine({})

# Add states
machine.add_state(create_state("start"), is_initial=True)
machine.add_state(create_state("end"))

# Add a transition with a potentially failing action
def risky_action(ctx, _):
    # This might fail
    result = 1 / 0  # Deliberate error
    return result

transition = create_transition("start", "end", "go", action=risky_action)
machine.add_transition(transition)

# Add an error listener
def on_transition_error(from_state, to_state, trigger, error):
    print(f"Error in transition from {from_state} to {to_state}: {error}")

machine.add_event_listener("transition_error", on_transition_error)

# Try the transition and handle the error
result = machine.trigger("go")
if result == TransitionResult.FAILED_ACTION:
    print("The transition action failed, but the state machine remains in a consistent state")
    print(f"Current state: {machine.current_state_name}")  # Still "start"
```

## Best Practices

1. **Keep states focused**: Each state should represent a single, well-defined stage in your process.

2. **Make states and transitions declarative**: Use the `create_state` and `create_transition` functions to make your state machine configuration clear and readable.

3. **Separate state machine logic from business logic**: The state machine should focus on managing states and transitions, while the actual business logic should be in the actions and guards.

4. **Use context for data sharing**: Store all data needed by states and transitions in the context object, rather than using external state.

5. **Validate transitions**: Use guard conditions to ensure transitions only occur when the system is in a valid state for them.

6. **Use event listeners for monitoring**: Instead of adding monitoring code directly to actions, use event listeners to decouple monitoring from core logic.

7. **Handle errors appropriately**: Always check transition results and handle errors, particularly when actions might fail.
