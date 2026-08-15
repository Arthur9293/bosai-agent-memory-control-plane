"""
permits.py — Permit issuance and atomic consumption logic.

PERMIT_SINGLE_USE=true
PERMIT_SCOPE_BOUND=true
PERMIT_MISSION_BOUND=true
PERMIT_EXPIRY_AWARE=true
PERMIT_REPLAYABLE=false
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Optional

from .domain import (
    ApprovalPermit,
    PermitStatus,
    Proposal,
    compute_scope_hash,
    now_utc,
)
from .persistence import MemoryRepository


DEFAULT_PERMIT_TTL_SECONDS = 3600  # 1 hour


def issue_permit(
    repo: MemoryRepository,
    mission_id: str,
    proposal: Proposal,
    *,
    ttl_seconds: int = DEFAULT_PERMIT_TTL_SECONDS,
) -> ApprovalPermit:
    """
    Issue a new single-use scoped permit for the given proposal.

    The scope hash cryptographically binds the permit to the exact:
    mission, proposal, action_type, target, from_state, to_state.

    Any tampering with these fields will invalidate the permit at the
    policy gate (DENIED_SCOPE_MISMATCH).
    """
    _now = now_utc()
    scope_hash = compute_scope_hash(
        mission_id=mission_id,
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        target=proposal.target,
        from_state=proposal.from_state,
        to_state=proposal.to_state,
    )
    permit = ApprovalPermit(
        permit_id=str(uuid.uuid4()),
        mission_id=mission_id,
        proposal_id=proposal.proposal_id,
        scope_hash=scope_hash,
        issued_at=_now,
        expires_at=_now + timedelta(seconds=ttl_seconds),
        consumed_at=None,
        status=PermitStatus.ACTIVE,
    )
    repo.save_permit(permit)
    return permit


def consume_permit(repo: MemoryRepository, permit: ApprovalPermit) -> ApprovalPermit:
    """
    Atomically mark a permit as CONSUMED.

    After this call, any further use of the same permit will be detected
    by the policy gate as DENIED_REPLAYED_PERMIT.

    Returns the updated permit object.
    """
    _now = now_utc()
    updated = ApprovalPermit(
        permit_id=permit.permit_id,
        mission_id=permit.mission_id,
        proposal_id=permit.proposal_id,
        scope_hash=permit.scope_hash,
        issued_at=permit.issued_at,
        expires_at=permit.expires_at,
        consumed_at=_now,
        status=PermitStatus.CONSUMED,
    )
    repo.update_permit(updated)
    return updated
