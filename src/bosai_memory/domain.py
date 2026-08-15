"""
domain.py — Core domain value objects and enumerations.

These are pure Python dataclasses with no external dependencies.
They carry no database or network concerns.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class MissionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ESCALATED = "ESCALATED"


class ProposalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"


class PermitStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class ServiceMode(str, Enum):
    NORMAL = "NORMAL"
    SAFE = "SAFE"
    DEGRADED = "DEGRADED"
    MAINTENANCE = "MAINTENANCE"


class ExecutionOutcome(str, Enum):
    EXECUTED = "EXECUTED"
    DENIED_NO_PERMIT = "DENIED_NO_PERMIT"
    DENIED_EXPIRED_PERMIT = "DENIED_EXPIRED_PERMIT"
    DENIED_REPLAYED_PERMIT = "DENIED_REPLAYED_PERMIT"
    DENIED_SCOPE_MISMATCH = "DENIED_SCOPE_MISMATCH"
    DENIED_MISSION_MISMATCH = "DENIED_MISSION_MISMATCH"
    DENIED_STATE_MISMATCH = "DENIED_STATE_MISMATCH"
    DENIED_POLICY = "DENIED_POLICY"
    READBACK_MISMATCH = "READBACK_MISMATCH"


class EventType(str, Enum):
    INCIDENT = "INCIDENT"
    RECOVERY = "RECOVERY"
    DEGRADATION = "DEGRADATION"
    OBSERVATION = "OBSERVATION"
    SYNTHETIC = "SYNTHETIC"


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OperationalVector:
    """
    3-dimensional deterministic operational similarity vector.
    Dimensions (all normalised to [0.0, 1.0]):
        [0] latency_pressure
        [1] error_pressure
        [2] dependency_risk_pressure
    """
    latency_pressure: float
    error_pressure: float
    dependency_risk_pressure: float

    def __post_init__(self) -> None:
        for dim_name, val in [
            ("latency_pressure", self.latency_pressure),
            ("error_pressure", self.error_pressure),
            ("dependency_risk_pressure", self.dependency_risk_pressure),
        ]:
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"{dim_name} must be in [0.0, 1.0], got {val}")

    def to_list(self) -> list[float]:
        return [self.latency_pressure, self.error_pressure, self.dependency_risk_pressure]

    def cosine_similarity(self, other: "OperationalVector") -> float:
        """Cosine similarity between two 3-D vectors."""
        a = self.to_list()
        b = other.to_list()
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x ** 2 for x in a) ** 0.5
        mag_b = sum(x ** 2 for x in b) ** 0.5
        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0
        return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# Domain entities
# ---------------------------------------------------------------------------

@dataclass
class Mission:
    mission_id: str
    incident_key: str
    status: MissionStatus
    observed_at: datetime
    context_json: dict = field(default_factory=dict)


@dataclass
class MemoryEvent:
    memory_event_id: str
    mission_id: str
    event_type: EventType
    content: str
    operational_vector: OperationalVector
    created_at: datetime


@dataclass
class Proposal:
    proposal_id: str
    mission_id: str
    action_type: str
    target: str
    from_state: str
    to_state: str
    rationale: str
    status: ProposalStatus
    created_at: datetime


@dataclass
class ApprovalPermit:
    permit_id: str
    mission_id: str
    proposal_id: str
    scope_hash: str
    issued_at: datetime
    expires_at: datetime
    consumed_at: Optional[datetime]
    status: PermitStatus


@dataclass
class ServiceState:
    service_id: str
    mode: ServiceMode
    version: int
    updated_at: datetime


@dataclass
class ExecutionReceipt:
    receipt_id: str
    mission_id: str
    proposal_id: str
    permit_id: Optional[str]
    outcome: ExecutionOutcome
    expected_state: str
    observed_state: str
    reason: str
    evidence_key: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# Scope hash computation
# ---------------------------------------------------------------------------

def compute_scope_hash(mission_id: str, proposal_id: str, action_type: str, target: str,
                       from_state: str, to_state: str) -> str:
    """
    Deterministic scope hash binding a permit to its exact execution context.
    Any deviation in these fields will produce a different hash → DENIED_SCOPE_MISMATCH.
    """
    payload = json.dumps({
        "mission_id": mission_id,
        "proposal_id": proposal_id,
        "action_type": action_type,
        "target": target,
        "from_state": from_state,
        "to_state": to_state,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)
