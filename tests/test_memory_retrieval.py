"""
tests/test_memory_retrieval.py — Vector similarity and memory retrieval tests.

Covers:
  TEST_10: nearest operational memory selected deterministically
"""

from __future__ import annotations

from bosai_memory.domain import OperationalVector
from bosai_memory.memory import retrieve_relevant_memory


# ---------------------------------------------------------------------------
# TEST_10: Nearest operational memory selected deterministically
# ---------------------------------------------------------------------------

def test_nearest_memory_selected_deterministically(repo, memory_events_seeded):
    """
    Target vector [0.8, 0.7, 0.6] should be closest to ALPHA [0.75, 0.65, 0.55]
    and furthest from BETA [0.1, 0.2, 0.9].

    This proves deterministic vector similarity ranking.
    Memory results are informational only — MEMORY_AUTHORITY=false.
    """
    target_vector = OperationalVector(0.8, 0.7, 0.6)
    alpha_vector = OperationalVector(0.75, 0.65, 0.55)
    beta_vector = OperationalVector(0.1, 0.2, 0.9)

    # Verify similarity ordering mathematically
    sim_to_alpha = target_vector.cosine_similarity(alpha_vector)
    sim_to_beta = target_vector.cosine_similarity(beta_vector)
    assert sim_to_alpha > sim_to_beta, (
        f"ALPHA similarity ({sim_to_alpha:.4f}) should exceed "
        f"BETA similarity ({sim_to_beta:.4f})"
    )

    # Verify repository retrieval returns ALPHA first
    results = retrieve_relevant_memory(repo, target_vector, limit=2)
    assert len(results) == 2

    # First result must be the ALPHA event (higher cosine similarity)
    assert results[0].operational_vector == alpha_vector, (
        f"Expected ALPHA vector {alpha_vector.to_list()} as nearest neighbour, "
        f"got {results[0].operational_vector.to_list()}"
    )

    # Second result is the BETA event (lower cosine similarity)
    assert results[1].operational_vector == beta_vector


def test_cosine_similarity_deterministic(repo, memory_events_seeded):
    """Repeated retrieval with the same vector always returns the same order."""
    target = OperationalVector(0.8, 0.7, 0.6)

    first_call = retrieve_relevant_memory(repo, target, limit=2)
    second_call = retrieve_relevant_memory(repo, target, limit=2)

    assert [e.memory_event_id for e in first_call] == [e.memory_event_id for e in second_call]


def test_identical_vector_similarity_is_one(repo):
    """A vector compared to itself has cosine similarity 1.0."""
    v = OperationalVector(0.5, 0.5, 0.5)
    assert abs(v.cosine_similarity(v) - 1.0) < 1e-9


def test_zero_vector_similarity_is_zero(repo):
    """Zero magnitude vector returns 0.0 similarity (no div-by-zero)."""
    v = OperationalVector(0.0, 0.0, 0.0)
    w = OperationalVector(0.5, 0.5, 0.5)
    assert v.cosine_similarity(w) == 0.0
    assert w.cosine_similarity(v) == 0.0


def test_orthogonal_vectors_similarity_is_zero(repo):
    """Orthogonal vectors have cosine similarity 0.0."""
    v = OperationalVector(1.0, 0.0, 0.0)
    w = OperationalVector(0.0, 1.0, 0.0)
    assert abs(v.cosine_similarity(w)) < 1e-9
