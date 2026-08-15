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

---

## ADR-002 — CockroachDB Persistent Memory Architecture

**Status:** Accepted

**Date:** 2025-08-15

**Decision:**
CockroachDB Serverless (Basic free tier) is the sole persistent memory store.
Memory is split into two layers:

1. **Transactional memory** (relational tables): missions, proposals,
   approval_permits, service_state, execution_receipts. ACID guarantees.
2. **Semantic memory** (vector-indexed table): memory_events with a VECTOR
   column and a CockroachDB vector index. Used for similarity-based retrieval
   of prior incidents.

No other database or in-memory store is used at runtime.

**Reason:**
- Single persistence layer minimizes operational complexity for a demo project.
- CockroachDB supports both relational (transactional) and vector (semantic)
  workloads natively, eliminating a Redis/Pinecone dependency.
- Serverless Basic free tier is sufficient for demo scale.
- Both memory modes are visible to judges via the schema and demo queries.

**Consequences:**
- All state is in CockroachDB. If the cluster is unavailable, the system
  fails closed (no ungoverned fallback).
- Vector index is non-authoritative by design (see ADR-001).
- Schema must be applied before application code runs (milestone 0D).

---

## ADR-003 — CockroachDB Competition Tool Selection

**Status:** Accepted

**Date:** 2025-08-15

**Decision:**

| Priority | Tool | Role |
|---|---|---|
| Primary 1 | Distributed Vector Indexing | Semantic memory retrieval at runtime |
| Primary 2 | Cloud Managed MCP Server | Agent tool interface for memory read/write |
| Optional 3 | ccloud CLI | Cluster provisioning and schema management (setup only) |

**Reason:**
- Distributed Vector Indexing is directly visible to judges: the schema has a
  VECTOR column; the demo shows a similarity query.
- Cloud Managed MCP Server elevates CockroachDB to a first-class agentic
  component rather than a plain database; MCP tool calls are visible in logs.
- ccloud CLI provides judge-visible provisioning evidence in the demo video
  without adding runtime complexity.
- Agent Skills Repo was considered but not selected: its integration would
  only be visible during development (coding tool use), which does not qualify
  as a runtime integration.

**Fallback:**
If the Cloud Managed MCP Server introduces unacceptable authentication
complexity, it is replaced with ccloud CLI as Tool 2 (see STACK-FREEZE.md
Fallback Architecture section). Vector Indexing is unconditional.

**Consequences:**
- Milestone 0D must configure MCP Server authentication before 0E begins.
- If MCP Server auth fails in 0D, the fallback is activated and STACK-FREEZE.md
  is updated with a bounded amendment commit.

---

## ADR-004 — AWS Minimal Runtime Architecture

**Status:** Accepted

**Date:** 2025-08-15

**Decision:**
The AWS execution layer uses:
- **AWS Lambda** (`python3.12`, 256 MB, 30s timeout, reserved concurrency 1)
- **Lambda Function URL** (HTTPS endpoint, no API Gateway)
- **Amazon S3** (private evidence bucket, versioning enabled)

No VPC, NAT Gateway, ECS, EKS, CloudFront, RDS, or SageMaker is used.

**Reason:**
- Lambda Function URL provides HTTPS access without API Gateway cost or
  configuration overhead.
- Lambda can connect to CockroachDB Serverless over public TLS (port 26257)
  without VPC peering — CockroachDB Serverless exposes a public endpoint.
- Reserved concurrency of 1 prevents parallel execution permit conflicts.
- S3 is the simplest durable evidence store at demo scale.
- Entire AWS footprint fits within the free tier.

**Consequences:**
- Lambda cold-start latency (~1-3s) is acceptable for a demo.
- If Lambda free tier is exhausted, cost is minimal (< $0.01 for demo scale).
- Explicit teardown of Lambda + S3 after submission prevents ongoing charges.

---

## ADR-005 — Deterministic Authority and Human GO

**Status:** Accepted

**Date:** 2025-08-15

**Decision:**
The Human GO permit is the only object that can authorize a consequential
execution. Permit validation is deterministic Python code, not LLM inference.

Human GO permits are:
- **Single-use**: consumed atomically at execution start.
- **Scope-bound**: must match exact action_type, target, from_state, to_state.
- **Mission-bound**: must reference the active mission.
- **Expiry-aware**: TTL of 5 minutes; expired permits are unconditionally rejected.
- **Non-replayable**: consumed flag prevents reuse even within the expiry window.

All five rejection cases (no permit, expired, replayed, scope mismatch,
mission mismatch) result in `EXECUTION=DENIED` and a written receipt.

**Reason:**
- A deterministic permit model is auditable, testable, and reproducible.
- Time-bounded permits prevent approvals from lingering indefinitely.
- Atomic consumption prevents race conditions in concurrent invocations.
- All five cases must be demonstrable for hackathon evidence.

**Consequences:**
- The UI/CLI must expose a clear Human GO action that writes an
  `approval_permits` record.
- The demo must show at least the DENIED_NO_PERMIT case before the approved path.
- Policy engine must be implemented as pure Python with no external calls.

---

## ADR-006 — Runtime and Model Strategy

**Status:** Accepted

**Date:** 2025-08-15

**Decision:**

```
RUNTIME_LANGUAGE=Python 3.12
PROPOSAL_GENERATION=deterministic rule-based Python (primary)
EMBEDDINGS=OpenAI text-embedding-3-small (optional; falls back gracefully)
LLM_SUMMARY=OpenAI gpt-4o-mini (optional; non-authoritative)
BEDROCK=not selected
LLM_AUTHORITY=false
```

**Reason:**
- Python 3.12 has native Lambda runtime support, excellent CockroachDB
  (psycopg2/psycopg3) and MCP SDK support, and is the fastest path for
  Bob-assisted development.
- Deterministic proposal generation ensures the demo is reproducible without
  a live LLM API dependency.
- OpenAI embeddings are optional — the system degrades gracefully if
  unavailable (zero-vector fallback).
- Amazon Bedrock is not selected because: (a) it adds IAM complexity and
  model-access request latency; (b) the authoritative governance paths require
  no LLM; (c) selecting Bedrock solely because AWS sponsors the hackathon
  would be dishonest about the architectural rationale.

**Consequences:**
- No LLM dependency is on the critical execution path.
- The demo remains functional if OpenAI is unavailable.
- Milestone 0E must package psycopg2-binary, mcp SDK, and boto3 into a
  Lambda deployment bundle.

---

## ADR-007 — Synthetic Demo Execution Boundary

**Status:** Accepted

**Date:** 2025-08-15

**Decision:**
The demo operates exclusively on synthetic data and a synthetic service.
The "managed service" is a row in the `service_state` CockroachDB table.
No real infrastructure, customer data, financial operations, or destructive
actions are performed at any point during the demo.

The demo scenario is fixed:
`synthetic-svc-01`: `NORMAL` → (incident) → proposal → Human GO → `SAFE`

**Reason:**
- A synthetic service eliminates all risk of accidental production impact.
- The governance model, CockroachDB memory, and AWS execution are fully
  demonstrated without needing real infrastructure to manage.
- Judges can reproduce the demo entirely from the public repository.
- The bounded action (mode transition) is unambiguous and visually clear.

**Consequences:**
- No real AWS infrastructure remediation is ever performed.
- The Lambda executor updates `service_state` in CockroachDB and writes to S3;
  it does not call any external service.
- This boundary is permanent for the hackathon submission.
