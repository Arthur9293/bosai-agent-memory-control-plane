# Architecture Decisions

This document records architectural decisions for the BOSAI Agent Memory
Control Plane. New ADRs must be added here before implementation that depends
on them begins.

---

## ADR-000 — Isolated Hackathon Repository

**Status:** Accepted

**Date:** 2025-08-15

**Decision:**
This hackathon implementation lives in a dedicated repository
(`Arthur9293/bosai-agent-memory-control-plane`) and must not modify existing
BOSAI systems.

**Reason:**
- Compliance: hackathon rules require a newly created project.
- Provenance clarity: keeps the source boundary between pre-existing BOSAI
  work and new hackathon implementation unambiguous and auditable.
- Reproducibility: judges and reviewers can clone a single repository and
  reproduce the entire demo without touching any pre-existing system.
- Cross-workstream contamination prevention: changes to protected BOSAI
  repositories could break unrelated production workstreams.

**Consequences:**
- All implementation code, schemas, infrastructure definitions, and
  documentation for this project live exclusively in this repository.
- Any reuse of pre-existing material must be explicitly declared in
  `docs/PROVENANCE.md`.

---

## ADR-001 — Persistent Memory Does Not Equal Authority

**Status:** Accepted

**Date:** 2025-08-15

**Decision:**
CockroachDB memory may inform proposals, but memory content or vector
similarity scores can never directly authorize consequential execution.
Authority remains deterministic and bounded by policy plus Human GO where
required.

**Reason:**
- An agent that can authorize its own actions by retrieving sufficiently
  similar past approvals has no meaningful authority boundary.
- Vector similarity is a retrieval heuristic, not a trust signal.
- Deterministic policy evaluation on bounded proposal schemas is auditable;
  similarity-based authorization is not.
- The Human GO gate ensures a human remains in the loop for consequential
  actions regardless of what memory contains.

**Consequences:**
- The governance engine must evaluate proposals against explicit policy rules,
  not past memory similarity.
- CockroachDB queries return context for proposal generation only.
- No code path may bypass the policy check or the Human GO gate based on
  memory content alone.
- This decision must be re-affirmed if any retrieval-augmented authorization
  pattern is proposed in a future milestone.
