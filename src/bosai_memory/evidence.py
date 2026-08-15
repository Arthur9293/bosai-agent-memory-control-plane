"""
evidence.py — Execution receipt and evidence record building.

EVIDENCE_REQUIRED=true
READBACK_REQUIRED=true

Evidence keys follow the pattern:
    evidence/<receipt_id>.json

The actual S3 upload is deferred to 0F (Lambda deployment milestone).
In 0E, the evidence_key is generated and stored in the receipt but the
object is not uploaded to S3.
"""

from __future__ import annotations

import uuid
from typing import Optional

from .domain import ExecutionOutcome, ExecutionReceipt, now_utc
from .persistence import MemoryRepository


def build_evidence_receipt(
    repo: MemoryRepository,
    *,
    mission_id: str,
    proposal_id: str,
    permit_id: Optional[str],
    outcome: ExecutionOutcome,
    expected_state: str,
    observed_state: str,
    reason: str,
    evidence_key: Optional[str] = None,
) -> ExecutionReceipt:
    """
    Build and persist an immutable execution receipt.

    Called for BOTH denied and executed outcomes — every gate decision
    produces a receipt. No denied action may mutate service_state (that
    invariant is enforced in handler.py before this is called).
    """
    receipt = ExecutionReceipt(
        receipt_id=str(uuid.uuid4()),
        mission_id=mission_id,
        proposal_id=proposal_id,
        permit_id=permit_id,
        outcome=outcome,
        expected_state=expected_state,
        observed_state=observed_state,
        reason=reason,
        evidence_key=evidence_key,
        created_at=now_utc(),
    )
    repo.save_receipt(receipt)
    return receipt


def make_evidence_key(receipt_id: str) -> str:
    """
    Produce an S3 object key for a receipt.
    The actual upload is deferred to 0F.
    """
    return f"evidence/{receipt_id}.json"
