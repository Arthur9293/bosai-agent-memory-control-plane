"""
memory.py — Memory retrieval module.

Retrieves operationally relevant past incidents by vector similarity.

MEMORY_AUTHORITY=false — a vector match influences the proposal but
never authorises execution.
"""

from __future__ import annotations

from .domain import MemoryEvent, OperationalVector
from .persistence import MemoryRepository


def retrieve_relevant_memory(
    repo: MemoryRepository,
    query_vector: OperationalVector,
    *,
    limit: int = 5,
) -> list[MemoryEvent]:
    """
    Return memory events ordered by cosine similarity to the query vector.

    The caller (handler/proposal builder) MAY use these results to enrich
    the rationale of a proposal.

    These results MUST NOT be used to authorise execution.
    Only a valid human-issued permit authorises execution.
    """
    return repo.get_nearest_memory_events(query_vector, limit=limit)
