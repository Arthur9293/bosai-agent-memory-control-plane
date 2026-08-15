"""
policy.py — Deterministic policy gate.

This module contains the single authority invariant:
  - A vector match MAY influence a proposal.
  - It may NEVER authorize execution.
  - Only a valid, unexpired, unconsumed, scope-bound, mission-bound permit
    may authorize execution.

POLICY_ENGINE=deterministic
LLM_AUTHORITY=false
VECTOR_AUTHORITY=false
"""

from __future__ import annotations

from datetime import datetime, timezone

from .domain import (
    ApprovalPermit,
    ExecutionOutcome,
    Proposal,
    PermitStatus,
    ServiceState,
    compute_scope_hash,
    now_utc,
)


class PolicyDenied(Exception):
    """Raised when policy rejects an execution attempt."""

    def __init__(self, outcome: ExecutionOutcome, reason: str) -> None:
        self.outcome = outcome
        self.reason = reason
        super().__init__(f"{outcome.value}: {reason}")


def validate_permit_for_proposal(
    permit: ApprovalPermit | None,
    proposal: Proposal,
    current_service_mode: str,
    *,
    now: datetime | None = None,
) -> None:
    """
    Validate that a permit authorises execution of a proposal.

    Raises PolicyDenied with the exact outcome code on any failure.

    Checks (in order):
      1. No permit at all                → DENIED_NO_PERMIT
      2. Mission mismatch                → DENIED_MISSION_MISMATCH
      3. Proposal mismatch               → (caught by scope hash)
      4. Scope hash mismatch             → DENIED_SCOPE_MISMATCH
      5. Permit expired                  → DENIED_EXPIRED_PERMIT
      6. Permit already consumed/revoked → DENIED_REPLAYED_PERMIT
      7. Current state ≠ proposal from   → DENIED_STATE_MISMATCH

    Authorisation invariants enforced here:
      MEMORY_AUTHORITY=false
      VECTOR_AUTHORITY=false
      LLM_AUTHORITY=false
      HUMAN_GO_REQUIRED=true
    """
    _now = now or now_utc()

    # 1. No permit
    if permit is None:
        raise PolicyDenied(ExecutionOutcome.DENIED_NO_PERMIT, "No permit presented.")

    # 2. Mission mismatch
    if permit.mission_id != proposal.mission_id:
        raise PolicyDenied(
            ExecutionOutcome.DENIED_MISSION_MISMATCH,
            f"Permit mission {permit.mission_id} does not match proposal mission {proposal.mission_id}.",
        )

    # 3. Scope hash mismatch
    expected_hash = compute_scope_hash(
        mission_id=proposal.mission_id,
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        target=proposal.target,
        from_state=proposal.from_state,
        to_state=proposal.to_state,
    )
    if permit.scope_hash != expected_hash:
        raise PolicyDenied(
            ExecutionOutcome.DENIED_SCOPE_MISMATCH,
            f"Permit scope hash does not match computed hash for this proposal.",
        )

    # 4. Permit expired
    if _now > permit.expires_at:
        raise PolicyDenied(
            ExecutionOutcome.DENIED_EXPIRED_PERMIT,
            f"Permit expired at {permit.expires_at.isoformat()}.",
        )

    # 5. Permit replayed / consumed / revoked
    if permit.status != PermitStatus.ACTIVE:
        raise PolicyDenied(
            ExecutionOutcome.DENIED_REPLAYED_PERMIT,
            f"Permit is not ACTIVE (status={permit.status.value}).",
        )
    if permit.consumed_at is not None:
        raise PolicyDenied(
            ExecutionOutcome.DENIED_REPLAYED_PERMIT,
            f"Permit was already consumed at {permit.consumed_at.isoformat()}.",
        )

    # 6. State mismatch — current service mode must match what the proposal expects
    if current_service_mode != proposal.from_state:
        raise PolicyDenied(
            ExecutionOutcome.DENIED_STATE_MISMATCH,
            f"Current service mode is '{current_service_mode}', "
            f"proposal expects '{proposal.from_state}'.",
        )
