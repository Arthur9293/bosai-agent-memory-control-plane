"""
persistence.py — Abstract persistence interface and in-memory fake adapter.

The domain policy is completely independent of CockroachDB-specific code.
Real credentials come ONLY from DATABASE_URL at runtime.

Adapters:
  - InMemoryRepository : deterministic fake for unit tests
  - CockroachDBRepository : live adapter for production (skeleton provided)
"""

from __future__ import annotations

import copy
import uuid
from abc import ABC, abstractmethod
from typing import Optional

from .domain import (
    ApprovalPermit,
    ExecutionReceipt,
    MemoryEvent,
    Mission,
    OperationalVector,
    Proposal,
    ServiceState,
    PermitStatus,
)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class MemoryRepository(ABC):

    @abstractmethod
    def save_mission(self, mission: Mission) -> None: ...

    @abstractmethod
    def get_mission(self, mission_id: str) -> Optional[Mission]: ...

    @abstractmethod
    def save_memory_event(self, event: MemoryEvent) -> None: ...

    @abstractmethod
    def get_nearest_memory_events(
        self, query_vector: OperationalVector, limit: int = 5
    ) -> list[MemoryEvent]:
        """Return events ordered by cosine similarity to query_vector (descending)."""
        ...

    @abstractmethod
    def save_proposal(self, proposal: Proposal) -> None: ...

    @abstractmethod
    def get_proposal(self, proposal_id: str) -> Optional[Proposal]: ...

    @abstractmethod
    def save_permit(self, permit: ApprovalPermit) -> None: ...

    @abstractmethod
    def get_permit(self, permit_id: str) -> Optional[ApprovalPermit]: ...

    @abstractmethod
    def update_permit(self, permit: ApprovalPermit) -> None: ...

    @abstractmethod
    def get_service_state(self, service_id: str) -> Optional[ServiceState]: ...

    @abstractmethod
    def update_service_state(self, state: ServiceState) -> None: ...

    @abstractmethod
    def save_receipt(self, receipt: ExecutionReceipt) -> None: ...

    @abstractmethod
    def get_receipt(self, receipt_id: str) -> Optional[ExecutionReceipt]: ...


# ---------------------------------------------------------------------------
# In-memory fake adapter (deterministic, no I/O — used in unit tests)
# ---------------------------------------------------------------------------

class InMemoryRepository(MemoryRepository):
    """
    Pure in-memory implementation for unit testing.
    All operations are deterministic and synchronous.
    No network, no database, no credentials required.
    """

    def __init__(self) -> None:
        self._missions: dict[str, Mission] = {}
        self._memory_events: dict[str, MemoryEvent] = {}
        self._proposals: dict[str, Proposal] = {}
        self._permits: dict[str, ApprovalPermit] = {}
        self._service_states: dict[str, ServiceState] = {}
        self._receipts: dict[str, ExecutionReceipt] = {}

    def save_mission(self, mission: Mission) -> None:
        self._missions[mission.mission_id] = copy.deepcopy(mission)

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        return copy.deepcopy(self._missions.get(mission_id))

    def save_memory_event(self, event: MemoryEvent) -> None:
        self._memory_events[event.memory_event_id] = copy.deepcopy(event)

    def get_nearest_memory_events(
        self, query_vector: OperationalVector, limit: int = 5
    ) -> list[MemoryEvent]:
        """
        Deterministic cosine similarity ranking.
        Mirrors what the CockroachDB vector index does at the DB layer.
        """
        scored: list[tuple[float, MemoryEvent]] = [
            (query_vector.cosine_similarity(e.operational_vector), copy.deepcopy(e))
            for e in self._memory_events.values()
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def save_proposal(self, proposal: Proposal) -> None:
        self._proposals[proposal.proposal_id] = copy.deepcopy(proposal)

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        return copy.deepcopy(self._proposals.get(proposal_id))

    def save_permit(self, permit: ApprovalPermit) -> None:
        self._permits[permit.permit_id] = copy.deepcopy(permit)

    def get_permit(self, permit_id: str) -> Optional[ApprovalPermit]:
        return copy.deepcopy(self._permits.get(permit_id))

    def update_permit(self, permit: ApprovalPermit) -> None:
        if permit.permit_id not in self._permits:
            raise KeyError(f"Permit {permit.permit_id} not found.")
        self._permits[permit.permit_id] = copy.deepcopy(permit)

    def get_service_state(self, service_id: str) -> Optional[ServiceState]:
        return copy.deepcopy(self._service_states.get(service_id))

    def update_service_state(self, state: ServiceState) -> None:
        self._service_states[state.service_id] = copy.deepcopy(state)

    def save_receipt(self, receipt: ExecutionReceipt) -> None:
        self._receipts[receipt.receipt_id] = copy.deepcopy(receipt)

    def get_receipt(self, receipt_id: str) -> Optional[ExecutionReceipt]:
        return copy.deepcopy(self._receipts.get(receipt_id))


# ---------------------------------------------------------------------------
# CockroachDB adapter — skeleton (live wiring deferred to 0F deployment)
# ---------------------------------------------------------------------------

class CockroachDBRepository(MemoryRepository):
    """
    CockroachDB persistence adapter.

    Credentials come exclusively from the DATABASE_URL environment variable
    at runtime. Never hardcode credentials.

    Usage:
        import os
        from bosai_memory.persistence import CockroachDBRepository
        repo = CockroachDBRepository(os.environ["DATABASE_URL"])
    """

    def __init__(self, database_url: str) -> None:
        # Deferred import: psycopg is only required at runtime, not in unit tests.
        import psycopg  # type: ignore
        self._conn = psycopg.connect(database_url)

    # ------------------------------------------------------------------
    # Missions
    # ------------------------------------------------------------------

    def save_mission(self, mission: Mission) -> None:
        import json
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO missions (mission_id, incident_key, status, observed_at, context_json)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (mission_id) DO UPDATE
                    SET status = EXCLUDED.status,
                        context_json = EXCLUDED.context_json
                """,
                (
                    mission.mission_id,
                    mission.incident_key,
                    mission.status.value,
                    mission.observed_at,
                    json.dumps(mission.context_json),
                ),
            )
        self._conn.commit()

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        from .domain import MissionStatus
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT mission_id, incident_key, status, observed_at, context_json "
                "FROM missions WHERE mission_id = %s",
                (mission_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return Mission(
            mission_id=str(row[0]),
            incident_key=row[1],
            status=MissionStatus(row[2]),
            observed_at=row[3],
            context_json=row[4],
        )

    # ------------------------------------------------------------------
    # Memory events
    # ------------------------------------------------------------------

    def save_memory_event(self, event: MemoryEvent) -> None:
        vec_str = str(event.operational_vector.to_list())
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_events
                    (memory_event_id, mission_id, event_type, content, operational_vector, created_at)
                VALUES (%s, %s, %s, %s, %s::VECTOR, %s)
                ON CONFLICT (memory_event_id) DO NOTHING
                """,
                (
                    event.memory_event_id,
                    event.mission_id,
                    event.event_type.value,
                    event.content,
                    vec_str,
                    event.created_at,
                ),
            )
        self._conn.commit()

    def get_nearest_memory_events(
        self, query_vector: OperationalVector, limit: int = 5
    ) -> list[MemoryEvent]:
        """Uses CockroachDB vector cosine distance (<=> operator) for ANN retrieval."""
        from .domain import EventType
        vec_str = str(query_vector.to_list())
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT memory_event_id, mission_id, event_type, content,
                       operational_vector, created_at
                FROM memory_events
                ORDER BY operational_vector <=> %s::VECTOR
                LIMIT %s
                """,
                (vec_str, limit),
            )
            rows = cur.fetchall()
        result = []
        for row in rows:
            raw_vec = row[4]  # CockroachDB returns vector as list or string
            if isinstance(raw_vec, str):
                import ast
                raw_vec = ast.literal_eval(raw_vec)
            ov = OperationalVector(*raw_vec)
            result.append(MemoryEvent(
                memory_event_id=str(row[0]),
                mission_id=str(row[1]),
                event_type=EventType(row[2]),
                content=row[3],
                operational_vector=ov,
                created_at=row[5],
            ))
        return result

    # ------------------------------------------------------------------
    # Proposals
    # ------------------------------------------------------------------

    def save_proposal(self, proposal: Proposal) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO proposals
                    (proposal_id, mission_id, action_type, target, from_state,
                     to_state, rationale, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (proposal_id) DO UPDATE
                    SET status = EXCLUDED.status
                """,
                (
                    proposal.proposal_id,
                    proposal.mission_id,
                    proposal.action_type,
                    proposal.target,
                    proposal.from_state,
                    proposal.to_state,
                    proposal.rationale,
                    proposal.status.value,
                    proposal.created_at,
                ),
            )
        self._conn.commit()

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        from .domain import ProposalStatus
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT proposal_id, mission_id, action_type, target, from_state, "
                "to_state, rationale, status, created_at "
                "FROM proposals WHERE proposal_id = %s",
                (proposal_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return Proposal(
            proposal_id=str(row[0]),
            mission_id=str(row[1]),
            action_type=row[2],
            target=row[3],
            from_state=row[4],
            to_state=row[5],
            rationale=row[6],
            status=ProposalStatus(row[7]),
            created_at=row[8],
        )

    # ------------------------------------------------------------------
    # Permits
    # ------------------------------------------------------------------

    def save_permit(self, permit: ApprovalPermit) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO approval_permits
                    (permit_id, mission_id, proposal_id, scope_hash,
                     issued_at, expires_at, consumed_at, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (permit_id) DO NOTHING
                """,
                (
                    permit.permit_id,
                    permit.mission_id,
                    permit.proposal_id,
                    permit.scope_hash,
                    permit.issued_at,
                    permit.expires_at,
                    permit.consumed_at,
                    permit.status.value,
                ),
            )
        self._conn.commit()

    def get_permit(self, permit_id: str) -> Optional[ApprovalPermit]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT permit_id, mission_id, proposal_id, scope_hash, "
                "issued_at, expires_at, consumed_at, status "
                "FROM approval_permits WHERE permit_id = %s",
                (permit_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return ApprovalPermit(
            permit_id=str(row[0]),
            mission_id=str(row[1]),
            proposal_id=str(row[2]),
            scope_hash=row[3],
            issued_at=row[4],
            expires_at=row[5],
            consumed_at=row[6],
            status=PermitStatus(row[7]),
        )

    def update_permit(self, permit: ApprovalPermit) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE approval_permits
                SET consumed_at = %s, status = %s
                WHERE permit_id = %s
                """,
                (permit.consumed_at, permit.status.value, permit.permit_id),
            )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Service state
    # ------------------------------------------------------------------

    def get_service_state(self, service_id: str) -> Optional[ServiceState]:
        from .domain import ServiceMode
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT service_id, mode, version, updated_at "
                "FROM service_state WHERE service_id = %s",
                (service_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return ServiceState(
            service_id=row[0],
            mode=ServiceMode(row[1]),
            version=row[2],
            updated_at=row[3],
        )

    def update_service_state(self, state: ServiceState) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO service_state (service_id, mode, version, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (service_id) DO UPDATE
                    SET mode = EXCLUDED.mode,
                        version = service_state.version + 1,
                        updated_at = EXCLUDED.updated_at
                """,
                (state.service_id, state.mode.value, state.version, state.updated_at),
            )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Receipts
    # ------------------------------------------------------------------

    def save_receipt(self, receipt: ExecutionReceipt) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO execution_receipts
                    (receipt_id, mission_id, proposal_id, permit_id,
                     outcome, expected_state, observed_state, reason,
                     evidence_key, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (receipt_id) DO NOTHING
                """,
                (
                    receipt.receipt_id,
                    receipt.mission_id,
                    receipt.proposal_id,
                    receipt.permit_id,
                    receipt.outcome.value,
                    receipt.expected_state,
                    receipt.observed_state,
                    receipt.reason,
                    receipt.evidence_key,
                    receipt.created_at,
                ),
            )
        self._conn.commit()

    def get_receipt(self, receipt_id: str) -> Optional[ExecutionReceipt]:
        from .domain import ExecutionOutcome
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT receipt_id, mission_id, proposal_id, permit_id, "
                "outcome, expected_state, observed_state, reason, evidence_key, created_at "
                "FROM execution_receipts WHERE receipt_id = %s",
                (receipt_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return ExecutionReceipt(
            receipt_id=str(row[0]),
            mission_id=str(row[1]),
            proposal_id=str(row[2]),
            permit_id=str(row[3]) if row[3] is not None else None,
            outcome=ExecutionOutcome(row[4]),
            expected_state=row[5],
            observed_state=row[6],
            reason=row[7],
            evidence_key=row[8],
            created_at=row[9],
        )
