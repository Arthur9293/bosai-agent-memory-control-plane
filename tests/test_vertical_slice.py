"""
tests/test_vertical_slice.py — End-to-end governed vertical slice test.

Proves the complete canonical flow:
  OBSERVE → RETRIEVE MEMORY → PROPOSE → POLICY CHECK →
  DENY WITHOUT PERMIT → HUMAN GO → EXECUTE → READBACK →
  EVIDENCE RECEIPT → REJECT PERMIT REPLAY

This test is entirely deterministic. No external calls.
"""

from __future__ import annotations

import uuid
from datetime import timedelta, timezone, datetime

from bosai_memory.domain import (
    ApprovalPermit,
    ExecutionOutcome,
    OperationalVector,
    PermitStatus,
    ServiceMode,
    ServiceState,
    compute_scope_hash,
    now_utc,
)
from bosai_memory.evidence import build_evidence_receipt
from bosai_memory.handler import (
    attempt_execution,
    build_proposal,
    observe_incident,
    retrieve_memory_for_incident,
)
from bosai_memory.persistence import InMemoryRepository


def test_full_vertical_slice():
    """
    Canonical end-to-end governed vertical slice:

    1.  Observe incident (new mission).
    2.  Retrieve memory — ALPHA is closest neighbour.
    3.  Build proposal: synthetic-svc-01 NORMAL → SAFE.
    4.  Attempt without permit → DENIED_NO_PERMIT (no state change).
    5.  Issue human GO permit (simulates human action).
    6.  Execute → NORMAL → SAFE.
    7.  Verify readback matches SAFE.
    8.  Verify receipt outcome = EXECUTED.
    9.  Attempt replay → DENIED_REPLAYED_PERMIT (state unchanged).
    10. Service remains SAFE after replay attempt.
    """
    repo = InMemoryRepository()

    # ── Seed service in NORMAL ──────────────────────────────────────────────
    repo.update_service_state(ServiceState(
        service_id="synthetic-svc-01",
        mode=ServiceMode.NORMAL,
        version=1,
        updated_at=now_utc(),
    ))

    # ── Seed historical memory events ───────────────────────────────────────
    from bosai_memory.domain import EventType, Mission, MissionStatus, MemoryEvent
    alpha_mid = str(uuid.uuid4())
    beta_mid = str(uuid.uuid4())
    repo.save_mission(Mission(alpha_mid, "INC-ALPHA", MissionStatus.CLOSED, now_utc(), {}))
    repo.save_mission(Mission(beta_mid, "INC-BETA", MissionStatus.CLOSED, now_utc(), {}))
    repo.save_memory_event(MemoryEvent(
        str(uuid.uuid4()), alpha_mid, EventType.INCIDENT,
        "High latency / errors. SAFE mode resolved.",
        OperationalVector(0.75, 0.65, 0.55), now_utc(),
    ))
    repo.save_memory_event(MemoryEvent(
        str(uuid.uuid4()), beta_mid, EventType.INCIDENT,
        "Dependency cascade. Rolling restart.",
        OperationalVector(0.1, 0.2, 0.9), now_utc(),
    ))

    # ── Step 1: Observe incident ────────────────────────────────────────────
    mission = observe_incident(
        repo,
        incident_key="SYNTHETIC-INCIDENT-0E",
        context={"severity": "HIGH", "service": "synthetic-svc-01"},
    )
    assert repo.get_mission(mission.mission_id) is not None

    # ── Step 2: Retrieve memory (nearest neighbour) ─────────────────────────
    target_vector = OperationalVector(0.8, 0.7, 0.6)
    memories = retrieve_memory_for_incident(repo, target_vector, limit=2)
    assert len(memories) == 2
    # ALPHA must be the closest
    assert memories[0].operational_vector == OperationalVector(0.75, 0.65, 0.55)

    # ── Step 3: Build proposal ───────────────────────────────────────────────
    nearest_content = memories[0].content
    rationale = (
        f"Nearest prior incident: '{nearest_content}'. "
        "Deterministic policy proposes SAFE mode transition."
    )
    proposal = build_proposal(
        repo,
        mission_id=mission.mission_id,
        action_type="MODE_TRANSITION",
        target="synthetic-svc-01",
        from_state="NORMAL",
        to_state="SAFE",
        rationale=rationale,
    )
    assert repo.get_proposal(proposal.proposal_id) is not None

    # ── Step 4: Deny without permit ──────────────────────────────────────────
    denied = attempt_execution(repo, proposal, permit_id=None)
    assert denied.outcome == ExecutionOutcome.DENIED_NO_PERMIT
    assert denied.permit_consumed is False
    # State unchanged
    assert repo.get_service_state("synthetic-svc-01").mode == ServiceMode.NORMAL

    # ── Step 5: Human GO — issue permit ─────────────────────────────────────
    # Simulates human clicking approve in the Control Plane UI.
    scope_hash = compute_scope_hash(
        mission_id=mission.mission_id,
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        target=proposal.target,
        from_state=proposal.from_state,
        to_state=proposal.to_state,
    )
    _now = now_utc()
    permit = ApprovalPermit(
        permit_id=str(uuid.uuid4()),
        mission_id=mission.mission_id,
        proposal_id=proposal.proposal_id,
        scope_hash=scope_hash,
        issued_at=_now,
        expires_at=_now + timedelta(hours=1),
        consumed_at=None,
        status=PermitStatus.ACTIVE,
    )
    repo.save_permit(permit)

    # ── Step 6: Execute approved transition ──────────────────────────────────
    result = attempt_execution(repo, proposal, permit_id=permit.permit_id)
    assert result.outcome == ExecutionOutcome.EXECUTED
    assert result.permit_consumed is True
    assert result.observed_state == "SAFE"
    assert result.expected_state == "SAFE"

    # ── Step 7: Readback verification ────────────────────────────────────────
    post_state = repo.get_service_state("synthetic-svc-01")
    assert post_state.mode == ServiceMode.SAFE

    # ── Step 8: Receipt recorded ─────────────────────────────────────────────
    assert result.receipt_id is not None

    # ── Step 9: Replay attempt ───────────────────────────────────────────────
    replay = attempt_execution(repo, proposal, permit_id=permit.permit_id)
    assert replay.outcome == ExecutionOutcome.DENIED_REPLAYED_PERMIT
    assert replay.permit_consumed is False

    # ── Step 10: State unchanged after replay ────────────────────────────────
    final_state = repo.get_service_state("synthetic-svc-01")
    assert final_state.mode == ServiceMode.SAFE, (
        "Service state must not change after replayed permit denial."
    )
