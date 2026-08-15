"""
tests/test_domain.py — Domain value object tests.
"""

from __future__ import annotations

import pytest
from bosai_memory.domain import OperationalVector, compute_scope_hash


def test_operational_vector_valid():
    v = OperationalVector(0.5, 0.3, 0.8)
    assert v.to_list() == [0.5, 0.3, 0.8]


def test_operational_vector_boundary_values():
    v = OperationalVector(0.0, 0.0, 0.0)
    w = OperationalVector(1.0, 1.0, 1.0)
    assert v.to_list() == [0.0, 0.0, 0.0]
    assert w.to_list() == [1.0, 1.0, 1.0]


def test_operational_vector_invalid_below_zero():
    with pytest.raises(ValueError, match="latency_pressure"):
        OperationalVector(-0.1, 0.5, 0.5)


def test_operational_vector_invalid_above_one():
    with pytest.raises(ValueError, match="error_pressure"):
        OperationalVector(0.5, 1.1, 0.5)


def test_scope_hash_deterministic():
    h1 = compute_scope_hash("m1", "p1", "MODE", "svc", "NORMAL", "SAFE")
    h2 = compute_scope_hash("m1", "p1", "MODE", "svc", "NORMAL", "SAFE")
    assert h1 == h2


def test_scope_hash_changes_on_mutation():
    base = compute_scope_hash("m1", "p1", "MODE", "svc", "NORMAL", "SAFE")
    tampered = compute_scope_hash("m1", "p1", "MODE", "svc", "NORMAL", "DEGRADED")
    assert base != tampered


def test_scope_hash_is_hex_string():
    h = compute_scope_hash("m1", "p1", "MODE", "svc", "NORMAL", "SAFE")
    assert len(h) == 64  # SHA-256 hex digest
    int(h, 16)           # must be valid hexadecimal
