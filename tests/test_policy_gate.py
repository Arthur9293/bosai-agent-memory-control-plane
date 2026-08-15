"""
tests/test_policy_gate.py — Deterministic policy gate tests.

Covers:
  TEST_01: no permit → denied
  TEST_02: expired permit → denied
  TEST_03: scope mismatch → denied
  TEST_04: mission mismatch → denied
  TEST_05: valid permit → NORMAL→SAFE
  TEST_06: permit consumed once (execution consumes permit)
  TEST_07: replay → denied
  TEST_08: readback match → verified
  TEST_09: readback mismatch → fail closed
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from bosai_memory.domain import (
    ApprovalPermit,
    ExecutionOutcome,
    PermitStatus,
    ServiceMode,
    compute_scope_hash,
    now_utc,
)
from bosai_memory.handler import attempt_execution
from bosai_memory.persistence import InMemoryRepository
from bosai_memory.policy import PolicyDenied, validate_permit_for_proposal
from bosai_memory.service import verify_readback, ReadbackMismatch


# ---------------------------------------------------------------------------
# TEST_01: No permit → DENIED_NO_PERMIT
# ---------------------------------------------------------------------------

def test_no_permit_denied(repo, proposal, service_normal):
    """Execution without any permit is denied. Service state unchanged."""
    result = attempt_execution(repo, proposal, permit_id=None)

    assert result.outcome == ExecutionOutcome.DENIED_NO_PERMIT
    assert result.permit_consumed is False

    # Service state must remain NORMAL
    state = repo.get_service_state("synthetic-svc-01")
    assert state.mode == ServiceMode.NORMAL


# ---------------------------------------------------------------------------
# TEST_02: Expired permit → DENIED_EXPIRED_PERMIT
# ---------------------------------------------------------------------------

def test_expired_permit_denied(repo, mission, proposal, service_normal):
    """An expired permit is rejected. Service state unchanged."""
    past = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    scope_hash = compute_scope_hash(
        mission_id=mission.mission_id,
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        target=proposal.target,
        from_state=proposal.from_state,
        to_state=proposal.to_state,
    )
    expired_permit = ApprovalPermit(
        permit_id=str(uuid.uuid4()),
        mission_id=mission.mission_id,
        proposal_id=proposal.proposal_id,
        scope_hash=scope_hash,
        issued_at=past - timedelta(hours=1),
        expires_at=past,           # already expired
        consumed_at=None,
        status=PermitStatus.ACTIVE,
    )
    repo.save_permit(expired_permit)

    result = attempt_execution(repo, proposal, permit_id=expired_permit.permit_id)

    assert result.outcome == ExecutionOutcome.DENIED_EXPIRED_PERMIT
    assert result.permit_consumed is False

    state = repo.get_service_state("synthetic-svc-01")
    assert state.mode == ServiceMode.NORMAL


# ---------------------------------------------------------------------------
# TEST_03: Scope mismatch → DENIED_SCOPE_MISMATCH
# ---------------------------------------------------------------------------

def test_scope_mismatch_denied(repo, mission, proposal, service_normal):
    """Permit with wrong scope hash is rejected."""
    tampered_permit = ApprovalPermit(
        permit_id=str(uuid.uuid4()),
        mission_id=mission.mission_id,
        proposal_id=proposal.proposal_id,
        scope_hash="deadbeef" * 8,   # wrong hash
        issued_at=now_utc(),
        expires_at=now_utc() + timedelta(hours=1),
        consumed_at=None,
        status=PermitStatus.ACTIVE,
    )
    repo.save_permit(tampered_permit)

    result = attempt_execution(repo, proposal, permit_id=tampered_permit.permit_id)

    assert result.outcome == ExecutionOutcome.DENIED_SCOPE_MISMATCH
    assert result.permit_consumed is False

    state = repo.get_service_state("synthetic-svc-01")
    assert state.mode == ServiceMode.NORMAL


# ---------------------------------------------------------------------------
# TEST_04: Mission mismatch → DENIED_MISSION_MISMATCH
# ---------------------------------------------------------------------------

def test_mission_mismatch_denied(repo, proposal, service_normal):
    """Permit for a different mission is rejected."""
    wrong_mission_id = str(uuid.uuid4())
    # Compute a valid scope hash but using a different mission_id
    scope_hash = compute_scope_hash(
        mission_id=wrong_mission_id,
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        target=proposal.target,
        from_state=proposal.from_state,
        to_state=proposal.to_state,
    )
    wrong_permit = ApprovalPermit(
        permit_id=str(uuid.uuid4()),
        mission_id=wrong_mission_id,      # different mission
        proposal_id=proposal.proposal_id,
        scope_hash=scope_hash,
        issued_at=now_utc(),
        expires_at=now_utc() + timedelta(hours=1),
        consumed_at=None,
        status=PermitStatus.ACTIVE,
    )
    repo.save_permit(wrong_permit)

    result = attempt_execution(repo, proposal, permit_id=wrong_permit.permit_id)

    assert result.outcome == ExecutionOutcome.DENIED_MISSION_MISMATCH
    assert result.permit_consumed is False

    state = repo.get_service_state("synthetic-svc-01")
    assert state.mode == ServiceMode.NORMAL


# ---------------------------------------------------------------------------
# TEST_05: Valid permit → NORMAL → SAFE
# ---------------------------------------------------------------------------

def test_valid_permit_executes_transition(repo, proposal, service_normal, active_permit):
    """Full approved path: valid permit transitions service from NORMAL to SAFE."""
    result = attempt_execution(repo, proposal, permit_id=active_permit.permit_id)

    assert result.outcome == ExecutionOutcome.EXECUTED
    assert result.observed_state == "SAFE"
    assert result.expected_state == "SAFE"

    # Verify state in repository
    state = repo.get_service_state("synthetic-svc-01")
    assert state.mode == ServiceMode.SAFE


# ---------------------------------------------------------------------------
# TEST_06: Permit consumed exactly once
# ---------------------------------------------------------------------------

def test_permit_consumed_exactly_once(repo, proposal, service_normal, active_permit):
    """After execution, permit status is CONSUMED and consumed_at is set."""
    result = attempt_execution(repo, proposal, permit_id=active_permit.permit_id)
    assert result.outcome == ExecutionOutcome.EXECUTED
    assert result.permit_consumed is True

    # Fetch updated permit
    updated = repo.get_permit(active_permit.permit_id)
    assert updated.status == PermitStatus.CONSUMED
    assert updated.consumed_at is not None


# ---------------------------------------------------------------------------
# TEST_07: Replay → DENIED_REPLAYED_PERMIT
# ---------------------------------------------------------------------------

def test_permit_replay_denied(repo, proposal, service_normal, active_permit):
    """After successful execution, reusing the same permit is denied."""
    # First execution succeeds
    first = attempt_execution(repo, proposal, permit_id=active_permit.permit_id)
    assert first.outcome == ExecutionOutcome.EXECUTED

    # State is now SAFE — reset to NORMAL so a replay could theoretically work
    # (we want to prove the permit block, not a state mismatch block)
    from bosai_memory.domain import ServiceMode, ServiceState
    repo.update_service_state(
        ServiceState(
            service_id="synthetic-svc-01",
            mode=ServiceMode.NORMAL,
            version=99,
            updated_at=now_utc(),
        )
    )

    # Attempt replay with the same permit
    second = attempt_execution(repo, proposal, permit_id=active_permit.permit_id)
    assert second.outcome == ExecutionOutcome.DENIED_REPLAYED_PERMIT
    assert second.permit_consumed is False

    # Service state must still be NORMAL (replay did not execute)
    state = repo.get_service_state("synthetic-svc-01")
    assert state.mode == ServiceMode.NORMAL


# ---------------------------------------------------------------------------
# TEST_08: Readback match → verified
# ---------------------------------------------------------------------------

def test_readback_match_verified(repo, proposal, service_normal, active_permit):
    """After execution to SAFE, verify_readback confirms the correct state."""
    result = attempt_execution(repo, proposal, permit_id=active_permit.permit_id)
    assert result.outcome == ExecutionOutcome.EXECUTED

    # Explicit readback verification
    post_state = verify_readback(repo, "synthetic-svc-01", ServiceMode.SAFE)
    assert post_state.mode == ServiceMode.SAFE


# ---------------------------------------------------------------------------
# TEST_09: Readback mismatch → FAIL CLOSED
# ---------------------------------------------------------------------------

def test_readback_mismatch_fail_closed(repo, service_normal):
    """verify_readback raises ReadbackMismatch when state does not match expectation."""
    # Service is NORMAL; we expect SAFE
    with pytest.raises(ReadbackMismatch) as exc_info:
        verify_readback(repo, "synthetic-svc-01", ServiceMode.SAFE)

    assert exc_info.value.expected == "SAFE"
    assert exc_info.value.observed == "NORMAL"


# ---------------------------------------------------------------------------
# Additional: State mismatch → DENIED_STATE_MISMATCH
# ---------------------------------------------------------------------------

def test_state_mismatch_denied(repo, mission, proposal, service_normal):
    """If service is not in the expected from_state, execution is denied."""
    from bosai_memory.domain import ServiceMode, ServiceState

    # Force service to SAFE (not NORMAL as proposal expects)
    repo.update_service_state(
        ServiceState(
            service_id="synthetic-svc-01",
            mode=ServiceMode.SAFE,
            version=5,
            updated_at=now_utc(),
        )
    )

    scope_hash = compute_scope_hash(
        mission_id=mission.mission_id,
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        target=proposal.target,
        from_state=proposal.from_state,
        to_state=proposal.to_state,
    )
    fresh_permit = ApprovalPermit(
        permit_id=str(uuid.uuid4()),
        mission_id=mission.mission_id,
        proposal_id=proposal.proposal_id,
        scope_hash=scope_hash,
        issued_at=now_utc(),
        expires_at=now_utc() + timedelta(hours=1),
        consumed_at=None,
        status=PermitStatus.ACTIVE,
    )
    repo.save_permit(fresh_permit)

    result = attempt_execution(repo, proposal, permit_id=fresh_permit.permit_id)

    assert result.outcome == ExecutionOutcome.DENIED_STATE_MISMATCH
    assert result.permit_consumed is False

    # Service must remain SAFE (the pre-existing state, not mutated)
    state = repo.get_service_state("synthetic-svc-01")
    assert state.mode == ServiceMode.SAFE
