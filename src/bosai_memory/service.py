"""
service.py — Service state transitions.

Implements the actual state transition after policy and permit validation
have both passed.

FAIL_CLOSED=true — readback mismatch is never reported as success.
"""

from __future__ import annotations

from .domain import ServiceMode, ServiceState, now_utc
from .persistence import MemoryRepository


class ReadbackMismatch(Exception):
    """Raised when the post-transition state does not match the expected state."""

    def __init__(self, expected: str, observed: str) -> None:
        self.expected = expected
        self.observed = observed
        super().__init__(f"Readback mismatch: expected={expected}, observed={observed}")


def execute_transition(
    repo: MemoryRepository,
    service_id: str,
    to_mode: ServiceMode,
) -> ServiceState:
    """
    Transition the service to the specified mode and return the new state.

    Does NOT check policy or permits — those must be validated before calling
    this function. See handler.py for the full governed flow.
    """
    _now = now_utc()
    current = repo.get_service_state(service_id)
    new_version = (current.version + 1) if current is not None else 1
    new_state = ServiceState(
        service_id=service_id,
        mode=to_mode,
        version=new_version,
        updated_at=_now,
    )
    repo.update_service_state(new_state)
    return new_state


def verify_readback(
    repo: MemoryRepository,
    service_id: str,
    expected_mode: ServiceMode,
) -> ServiceState:
    """
    Read the current service state and verify it matches the expected mode.

    FAIL_CLOSED: raises ReadbackMismatch if there is any discrepancy.
    A mismatch must never be reported as success.
    """
    observed = repo.get_service_state(service_id)
    if observed is None:
        raise ReadbackMismatch(expected=expected_mode.value, observed="NOT_FOUND")
    if observed.mode != expected_mode:
        raise ReadbackMismatch(
            expected=expected_mode.value,
            observed=observed.mode.value,
        )
    return observed
