"""
tests/conftest.py — Shared fixtures for BOSAI memory governed vertical slice tests.

All fixtures are deterministic and require no external connections.
No OpenAI, Bedrock, or database calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from bosai_memory.domain import (
    EventType,
    MemoryEvent,
    Mission,
    MissionStatus,
    OperationalVector,
    Proposal,
    ProposalStatus,
    ServiceMode,
    ServiceState,
    compute_scope_hash,
    now_utc,
)
from bosai_memory.persistence import InMemoryRepository


def utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo() -> InMemoryRepository:
    """Fresh in-memory repository for each test."""
    return InMemoryRepository()


@pytest.fixture
def mission(repo: InMemoryRepository) -> Mission:
    m = Mission(
        mission_id=str(uuid.uuid4()),
        incident_key="TEST-INCIDENT-001",
        status=MissionStatus.OPEN,
        observed_at=now_utc(),
        context_json={"severity": "HIGH", "service": "synthetic-svc-01"},
    )
    repo.save_mission(m)
    return m


@pytest.fixture
def service_normal(repo: InMemoryRepository) -> ServiceState:
    state = ServiceState(
        service_id="synthetic-svc-01",
        mode=ServiceMode.NORMAL,
        version=1,
        updated_at=now_utc(),
    )
    repo.update_service_state(state)
    return state


@pytest.fixture
def proposal(repo: InMemoryRepository, mission: Mission) -> Proposal:
    p = Proposal(
        proposal_id=str(uuid.uuid4()),
        mission_id=mission.mission_id,
        action_type="MODE_TRANSITION",
        target="synthetic-svc-01",
        from_state="NORMAL",
        to_state="SAFE",
        rationale="High latency and error pressure detected. Vector similarity supports SAFE mode.",
        status=ProposalStatus.PENDING,
        created_at=now_utc(),
    )
    repo.save_proposal(p)
    return p


@pytest.fixture
def valid_scope_hash(mission: Mission, proposal: Proposal) -> str:
    return compute_scope_hash(
        mission_id=mission.mission_id,
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        target=proposal.target,
        from_state=proposal.from_state,
        to_state=proposal.to_state,
    )


@pytest.fixture
def active_permit(
    repo: InMemoryRepository,
    mission: Mission,
    proposal: Proposal,
    valid_scope_hash: str,
) -> "ApprovalPermit":
    from bosai_memory.domain import ApprovalPermit, PermitStatus
    _now = now_utc()
    permit = ApprovalPermit(
        permit_id=str(uuid.uuid4()),
        mission_id=mission.mission_id,
        proposal_id=proposal.proposal_id,
        scope_hash=valid_scope_hash,
        issued_at=_now,
        expires_at=_now + timedelta(hours=1),
        consumed_at=None,
        status=PermitStatus.ACTIVE,
    )
    repo.save_permit(permit)
    return permit


# ---------------------------------------------------------------------------
# Memory event fixtures (used for vector similarity tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def memory_events_seeded(repo: InMemoryRepository, mission: Mission) -> list[MemoryEvent]:
    """
    Two prior incidents:
    - ALPHA: [0.75, 0.65, 0.55] — close to target [0.8, 0.7, 0.6]
    - BETA:  [0.1,  0.2,  0.9]  — dissimilar control
    """
    alpha_mission_id = str(uuid.uuid4())
    beta_mission_id = str(uuid.uuid4())

    alpha_mission = Mission(
        mission_id=alpha_mission_id,
        incident_key="INCIDENT-2024-ALPHA",
        status=MissionStatus.CLOSED,
        observed_at=now_utc() - timedelta(hours=72),
        context_json={},
    )
    beta_mission = Mission(
        mission_id=beta_mission_id,
        incident_key="INCIDENT-2024-BETA",
        status=MissionStatus.CLOSED,
        observed_at=now_utc() - timedelta(hours=48),
        context_json={},
    )
    repo.save_mission(alpha_mission)
    repo.save_mission(beta_mission)

    alpha_event = MemoryEvent(
        memory_event_id=str(uuid.uuid4()),
        mission_id=alpha_mission_id,
        event_type=EventType.INCIDENT,
        content="High latency and high error rate. Resolved via SAFE mode.",
        operational_vector=OperationalVector(0.75, 0.65, 0.55),
        created_at=now_utc() - timedelta(hours=72),
    )
    beta_event = MemoryEvent(
        memory_event_id=str(uuid.uuid4()),
        mission_id=beta_mission_id,
        event_type=EventType.INCIDENT,
        content="Low latency, low errors, high dependency risk. Rolling restart.",
        operational_vector=OperationalVector(0.1, 0.2, 0.9),
        created_at=now_utc() - timedelta(hours=48),
    )
    repo.save_memory_event(alpha_event)
    repo.save_memory_event(beta_event)
    return [alpha_event, beta_event]
