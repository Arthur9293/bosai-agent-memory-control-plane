"""
handler.py — Governed vertical slice orchestrator.

Implements the canonical BOSAI execution flow:

  OBSERVE
  → RETRIEVE MEMORY
  → PROPOSE
  → POLICY CHECK
  → DENY WITHOUT PERMIT        (returns receipt, no state mutation)
  → HUMAN GO PERMIT
  → EXECUTE SYNTHETIC STATE TRANSITION
  → READBACK
  → EVIDENCE RECEIPT
  → REJECT PERMIT REPLAY

Authority invariants enforced end-to-end:
  MEMORY_AUTHORITY=false
  VECTOR_AUTHORITY=false
  LLM_AUTHORITY=false
  POLICY_ENGINE=deterministic
  HUMAN_GO_REQUIRED=true
  PERMIT_SINGLE_USE=true
  FAIL_CLOSED=true
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timezone
from typing import Optional

from .domain import (
    EventType,
    ExecutionOutcome,
    MemoryEvent,
    Mission,
    MissionStatus,
    OperationalVector,
    Proposal,
    ProposalStatus,
    ServiceMode,
    ServiceState,
    now_utc,
)
from .evidence import build_evidence_receipt, make_evidence_key
from .memory import retrieve_relevant_memory
from .permits import consume_permit
from .persistence import MemoryRepository
from .policy import PolicyDenied, validate_permit_for_proposal
from .service import ReadbackMismatch, execute_transition, verify_readback


# ---------------------------------------------------------------------------
# Step 1: Observe incident
# ---------------------------------------------------------------------------

def observe_incident(
    repo: MemoryRepository,
    incident_key: str,
    context: dict,
) -> Mission:
    """
    Record a new mission for the observed incident.
    Returns the persisted Mission object.
    """
    mission = Mission(
        mission_id=str(uuid.uuid4()),
        incident_key=incident_key,
        status=MissionStatus.OPEN,
        observed_at=now_utc(),
        context_json=context,
    )
    repo.save_mission(mission)
    return mission


# ---------------------------------------------------------------------------
# Step 2: Retrieve relevant memory (vector similarity)
# ---------------------------------------------------------------------------

def retrieve_memory_for_incident(
    repo: MemoryRepository,
    query_vector: OperationalVector,
    *,
    limit: int = 5,
) -> list[MemoryEvent]:
    """
    Retrieve past memory events closest to the current operational vector.

    MEMORY_AUTHORITY=false: results are informational only.
    """
    return retrieve_relevant_memory(repo, query_vector, limit=limit)


# ---------------------------------------------------------------------------
# Step 3: Build proposal
# ---------------------------------------------------------------------------

def build_proposal(
    repo: MemoryRepository,
    mission_id: str,
    *,
    action_type: str,
    target: str,
    from_state: str,
    to_state: str,
    rationale: str,
) -> Proposal:
    """
    Build and persist a proposed state transition.

    The proposal is PENDING until a human issues a permit (HUMAN_GO_REQUIRED=true).
    The rationale MAY reference memory retrieval results but those results
    do NOT constitute authorisation.
    """
    proposal = Proposal(
        proposal_id=str(uuid.uuid4()),
        mission_id=mission_id,
        action_type=action_type,
        target=target,
        from_state=from_state,
        to_state=to_state,
        rationale=rationale,
        status=ProposalStatus.PENDING,
        created_at=now_utc(),
    )
    repo.save_proposal(proposal)
    return proposal


# ---------------------------------------------------------------------------
# Step 4–9: Governed execution (policy gate → permit → execute → readback)
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    receipt_id: str
    outcome: ExecutionOutcome
    expected_state: str
    observed_state: str
    reason: str
    permit_consumed: bool
    evidence_key: Optional[str]


def attempt_execution(
    repo: MemoryRepository,
    proposal: Proposal,
    permit_id: Optional[str],
    *,
    now=None,
) -> ExecutionResult:
    """
    Governed execution gate:

    1. Fetch current service state.
    2. Validate permit (policy gate — deterministic, fail-closed).
    3. If denied → persist receipt, return denial.  No state mutation.
    4. Atomically consume permit.
    5. Execute state transition.
    6. Readback and compare.
    7. Persist receipt (success or readback mismatch).

    FAIL_CLOSED=true: readback mismatch outcome is READBACK_MISMATCH,
    never EXECUTED.
    """
    service_state = repo.get_service_state(proposal.target)
    current_mode = service_state.mode.value if service_state else "NOT_FOUND"

    permit = repo.get_permit(permit_id) if permit_id else None

    # Policy gate
    try:
        validate_permit_for_proposal(
            permit,
            proposal,
            current_mode,
            now=now,
        )
    except PolicyDenied as exc:
        receipt = build_evidence_receipt(
            repo,
            mission_id=proposal.mission_id,
            proposal_id=proposal.proposal_id,
            permit_id=permit_id,
            outcome=exc.outcome,
            expected_state=proposal.to_state,
            observed_state=current_mode,
            reason=exc.reason,
        )
        return ExecutionResult(
            receipt_id=receipt.receipt_id,
            outcome=exc.outcome,
            expected_state=proposal.to_state,
            observed_state=current_mode,
            reason=exc.reason,
            permit_consumed=False,
            evidence_key=None,
        )

    # Atomically consume permit — after this point it cannot be replayed.
    consume_permit(repo, permit)

    # Execute state transition
    to_mode = ServiceMode(proposal.to_state)
    execute_transition(repo, proposal.target, to_mode)

    # Readback
    try:
        post_state = verify_readback(repo, proposal.target, to_mode)
        observed_mode = post_state.mode.value
        outcome = ExecutionOutcome.EXECUTED
        reason = f"Transition to {to_mode.value} completed and verified."
    except ReadbackMismatch as rm:
        observed_mode = rm.observed
        outcome = ExecutionOutcome.READBACK_MISMATCH
        reason = f"Readback mismatch: expected={proposal.to_state}, observed={rm.observed}."

    evidence_key = make_evidence_key(str(uuid.uuid4()))
    receipt = build_evidence_receipt(
        repo,
        mission_id=proposal.mission_id,
        proposal_id=proposal.proposal_id,
        permit_id=permit_id,
        outcome=outcome,
        expected_state=proposal.to_state,
        observed_state=observed_mode,
        reason=reason,
        evidence_key=evidence_key if outcome == ExecutionOutcome.EXECUTED else None,
    )
    return ExecutionResult(
        receipt_id=receipt.receipt_id,
        outcome=outcome,
        expected_state=proposal.to_state,
        observed_state=observed_mode,
        reason=reason,
        permit_consumed=True,
        evidence_key=evidence_key if outcome == ExecutionOutcome.EXECUTED else None,
    )
