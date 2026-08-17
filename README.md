# BOSAI Agent Memory Control Plane

> **Memory informs proposals. Memory never authorizes execution.**

BOSAI is a governed agentic-memory control plane built for the CockroachDB × AWS Hackathon.

**Public judge demo:** https://arthur9293.github.io/bosai-agent-memory-control-plane/

## Architecture
`OBSERVE → RETRIEVE MEMORY → PROPOSE → POLICY CHECK → HUMAN GO → READBACK → EVIDENCE`

CockroachDB is the persistent system of record with six live tables: `missions`, `memory_events`, `proposals`, `approval_permits`, `service_state`, and `execution_receipts`.

Semantic memory uses native `VECTOR(3)` plus CockroachDB Distributed Vector Indexing. Verified target `[0.8,0.7,0.6]` ranks `INCIDENT-2024-ALPHA` first (~0.000039) and `INCIDENT-2024-BETA` second (~0.328616).

## CockroachDB Tools
- Cloud Managed MCP Server — configured read-only for auditable memory inspection.
- Distributed Vector Indexing — semantic retrieval alongside transactional memory.

## Governance
`MEMORY_AUTHORITY=false` · `VECTOR_AUTHORITY=false` · `LLM_AUTHORITY=false`

Consequential actions require deterministic policy and explicit, scoped, single-use Human GO permits.

## AWS
Amazon S3 evidence storage is provisioned with public access blocked, versioning enabled, and AES256 encryption.

**AWS Lambda — Deployment Quota Under Review.** The Python 3.12 readback runtime is implemented and packaged, but live deployment is not claimed complete while AWS reviews the new-account concurrency quota.

## Tests
**35 passed.** Coverage includes policy gates, permit replay denial, vector retrieval, fail-closed readback, Lambda read-only behavior, and secret protections.

## Run locally
`python3.12 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'`

Set `DATABASE_URL` locally, apply `schema/001_init.sql` and `schema/002_seed_demo.sql`, then run `PYTHONPATH=src pytest -q`.

## Provenance & License
The BOSAI concept predates the hackathon; this repository implementation was created during the submission period. See `docs/PROVENANCE.md`.

MIT License — see `LICENSE`.