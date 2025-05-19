"""
Example of using the state machine framework.

This module demonstrates how to use the state machine framework
to model a simple document approval workflow.
"""

from typing import Any, Dict, Optional

from .base import BaseStateMachine, create_state, create_transition


def create_document_workflow() -> BaseStateMachine:
    """
    Create a state machine that models a document approval workflow.

    The workflow has the following states:
    - draft: Document is being drafted
    - review: Document is being reviewed
    - approved: Document has been approved
    - rejected: Document has been rejected

    Returns:
        A configured state machine instance
    """
    # Create a context with document data
    context: Dict[str, Any] = {
        "document": {
            "title": "Example Document",
            "content": "This is a document that needs approval.",
            "status": "draft",
            "approvals": 0,
            "review_comments": [],
        }
    }

    # Create a state machine
    workflow = BaseStateMachine(context)

    # Define state actions
    def on_enter_draft(ctx: Dict[str, Any]) -> None:
        """Called when entering the draft state."""
        ctx["document"]["status"] = "draft"
        print(f"Document '{ctx['document']['title']}' is now in draft state.")

    def on_enter_review(ctx: Dict[str, Any]) -> None:
        """Called when entering the review state."""
        ctx["document"]["status"] = "in_review"
        print(f"Document '{ctx['document']['title']}' is now under review.")

    def on_enter_approved(ctx: Dict[str, Any]) -> None:
        """Called when entering the approved state."""
        ctx["document"]["status"] = "approved"
        print(f"Document '{ctx['document']['title']}' has been approved!")

    def on_enter_rejected(ctx: Dict[str, Any]) -> None:
        """Called when entering the rejected state."""
        ctx["document"]["status"] = "rejected"
        print(f"Document '{ctx['document']['title']}' has been rejected.")

    # Create states
    draft = create_state("draft", on_enter_draft)
    review = create_state("review", on_enter_review)
    approved = create_state("approved", on_enter_approved)
    rejected = create_state("rejected", on_enter_rejected)

    # Add states to the state machine
    workflow.add_state(draft, is_initial=True)
    workflow.add_state(review)
    workflow.add_state(approved)
    workflow.add_state(rejected)

    # Define transition actions
    def submit_action(ctx: Dict[str, Any], _: Optional[Any] = None) -> None:
        """Called when submitting a document for review."""
        print(f"Submitting document '{ctx['document']['title']}' for review.")

    def add_approval(ctx: Dict[str, Any], _: Optional[Any] = None) -> None:
        """Called when approving a document."""
        ctx["document"]["approvals"] += 1
        print(
            f"Added approval. Document now has {ctx['document']['approvals']} approvals."
        )

    def add_rejection_comment(
        ctx: Dict[str, Any], event: Optional[Dict[str, Any]]
    ) -> None:
        """Called when rejecting a document."""
        if event and "comment" in event:
            ctx["document"]["review_comments"].append(event["comment"])
            print(f"Added rejection comment: {event['comment']}")

    def clear_approvals(ctx: Dict[str, Any], _: Optional[Any] = None) -> None:
        """Called when resubmitting a document."""
        ctx["document"]["approvals"] = 0
        print("Cleared previous approvals for resubmission.")

    # Define guard conditions
    def has_enough_approvals(ctx: Dict[str, Any], _: Optional[Any] = None) -> bool:
        """Check if the document has enough approvals to be approved."""
        # Require at least 2 approvals to approve the document
        return ctx["document"]["approvals"] >= 2

    # Create transitions
    submit = create_transition("draft", "review", "submit", action=submit_action)
    approve = create_transition(
        "review", "approved", "approve", guard=has_enough_approvals, action=add_approval
    )
    reject = create_transition(
        "review", "rejected", "reject", action=add_rejection_comment
    )
    add_approval_transition = create_transition(
        "review", "review", "add_approval", action=add_approval
    )
    resubmit = create_transition(
        "rejected", "review", "resubmit", action=clear_approvals
    )
    revise = create_transition("review", "draft", "revise")

    # Add transitions to the state machine
    workflow.add_transition(submit)
    workflow.add_transition(approve)
    workflow.add_transition(reject)
    workflow.add_transition(add_approval_transition)
    workflow.add_transition(resubmit)
    workflow.add_transition(revise)

    # Add event listeners for monitoring
    def on_transition_start(from_state: str, to_state: str, trigger: str) -> None:
        """Called when a transition starts."""
        print(f"Starting transition from {from_state} to {to_state} via {trigger}")

    def on_transition_complete(from_state: str, to_state: str, trigger: str) -> None:
        """Called when a transition completes."""
        print(f"Completed transition from {from_state} to {to_state} via {trigger}")

    def on_guard_failed(state: str, trigger: str) -> None:
        """Called when a guard condition fails."""
        print(f"Guard condition failed for transition from {state} via {trigger}")

    # Register event listeners
    workflow.add_event_listener("transition_start", on_transition_start)
    workflow.add_event_listener("transition_complete", on_transition_complete)
    workflow.add_event_listener("guard_failed", on_guard_failed)

    return workflow


def run_example() -> None:
    """Run the document workflow example."""
    # Create the workflow
    workflow = create_document_workflow()

    # Show the initial state
    print(f"Initial state: {workflow.current_state_name}")

    # Submit the document for review
    workflow.trigger("submit")

    # Try to approve the document (should fail due to not enough approvals)
    workflow.trigger("approve")

    # Add two approvals
    workflow.trigger("add_approval")
    workflow.trigger("add_approval")

    # Now the approval should succeed
    workflow.trigger("approve")

    # Reset the workflow
    workflow.reset()

    # Try a different path (rejection and resubmission)
    workflow.trigger("submit")
    workflow.trigger("reject", {"comment": "Needs more details in section 3."})
    workflow.trigger("resubmit")

    # Decide to revise instead of continuing with the review
    workflow.trigger("revise")

    # Show the final state and history
    print(f"Final state: {workflow.current_state_name}")
    print(f"State history: {workflow.history}")

    # Show the document's final status
    document = workflow.context["document"]
    print(f"Document status: {document['status']}")
    print(f"Document approvals: {document['approvals']}")
    print(f"Review comments: {document['review_comments']}")


if __name__ == "__main__":
    run_example()
