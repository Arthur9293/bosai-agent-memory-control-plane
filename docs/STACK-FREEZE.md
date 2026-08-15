<!--
MILESTONE=BOSAI_COCKROACHDB_AWS_0C
STATUS=FROZEN
IMPLEMENTATION_STARTED=false
-->

# BOSAI CockroachDB × AWS — Stack Freeze

## Status

```
MILESTONE=BOSAI_COCKROACHDB_AWS_0C
STATUS=FROZEN
IMPLEMENTATION_STARTED=false
FROZEN_DATE=2026-08-15
FROZEN_BY=IBM Bob (bounded architecture agent)
AUTHORIZED_BY=Arthur Franck (Human GO)
```

This document records the single frozen architecture for the
**BOSAI Agent Memory Control Plane** hackathon submission.
No alternatives are left open. No further architecture decisions are required
before implementation begins.

---

## Competition Constraints

**Hackathon:** CockroachDB × AWS Hackathon — Build with Agentic Memory

| Requirement | Target | Status |
|---|---|---|
| Newly created project (during submission period) | This repository, created 2026-08-15 | ✅ Met |
| CockroachDB as persistent memory | Primary memory layer | ✅ Addressed |
| At least 2 eligible CockroachDB tools | Distributed Vector Indexing + Cloud Managed MCP Server | ✅ Addressed |
| At least 1 AWS service | Lambda + S3 | ✅ Addressed |
| Meaningful / visible integration | Judge-visible at runtime | ✅ Addressed |
| Public open-source repository | github.com/Arthur9293/bosai-agent-memory-control-plane | ✅ Met |
| Functional demo | End-to-end vertical slice | ✅ Addressed |
| Public video ≤ 3 minutes | YouTube / Vimeo | Planned |
| Visible CockroachDB memory behavior | Query logs + readback evidence | ✅ Addressed |

**Official sources:** See [Official Sources](#official-sources) section.

---

## Primary Architecture

```
PRIMARY_ARCHITECTURE=Lambda_Function_URL_Python_CockroachDB_Serverless
```

```
┌─────────────────────────────────────────────────────────────────┐
│                  BOSAI Agent Memory Control Plane               │
│                                                                 │
│  [CLI / Demo Client]  ←──────────────────────────────────────┐  │
│         │                                                     │  │
│         ▼                                                     │  │
│  ┌──────────────────┐   Lambda Function URL (HTTPS)          │  │
│  │  AWS Lambda      │ ◄─────────────────────────────────     │  │
│  │  Python 3.12     │                                        │  │
│  │                  │                                        │  │
│  │  [Control Plane] │                                        │  │
│  │   ┌────────────┐ │                                        │  │
│  │   │  OBSERVE   │ │                                        │  │
│  │   └─────┬──────┘ │                                        │  │
│  │         │        │                                        │  │
│  │   ┌─────▼──────┐ │  psycopg2 / TLS   ┌────────────────┐  │  │
│  │   │  RETRIEVE  │◄├──────────────────►│  CockroachDB   │  │  │
│  │   └─────┬──────┘ │   (port 26257)    │  Serverless    │  │  │
│  │         │        │                   │                │  │  │
│  │   ┌─────▼──────┐ │  MCP tool calls   │  ┌──────────┐ │  │  │
│  │   │  PROPOSE   │◄├──────────────────►│  │ Vector   │ │  │  │
│  │   └─────┬──────┘ │                   │  │ Index    │ │  │  │
│  │         │        │                   │  └──────────┘ │  │  │
│  │   ┌─────▼──────┐ │                   │  ┌──────────┐ │  │  │
│  │   │  POLICY    │ │                   │  │ Tables   │ │  │  │
│  │   │  CHECK     │ │                   │  │ (KV+TX)  │ │  │  │
│  │   └─────┬──────┘ │                   │  └──────────┘ │  │  │
│  │         │        │                   └────────────────┘  │  │
│  │   ┌─────▼──────┐ │                                        │  │
│  │   │  HUMAN GO  │─┼────────────────────────────────────────┘  │
│  │   │  GATE      │ │  (permit validated before execution)       │
│  │   └─────┬──────┘ │                                           │
│  │         │        │                                           │
│  │   ┌─────▼──────┐ │  write evidence   ┌────────────────┐      │
│  │   │  EXECUTE   │─┼──────────────────►│  Amazon S3     │      │
│  │   └─────┬──────┘ │                   │  (private)     │      │
│  │         │        │                   └────────────────┘      │
│  │   ┌─────▼──────┐ │  write-back       ┌────────────────┐      │
│  │   │  PERSIST   │─┼──────────────────►│  CockroachDB   │      │
│  │   └─────┬──────┘ │                   └────────────────┘      │
│  │         │        │                                           │
│  │   ┌─────▼──────┐ │  query            ┌────────────────┐      │
│  │   │  READBACK  │─┼──────────────────►│  CockroachDB   │      │
│  │   └─────┬──────┘ │                   └────────────────┘      │
│  │         │        │                                           │
│  │   ┌─────▼──────┐ │                                           │
│  │   │  PROVE     │ │  (terminal / API response)                │
│  │   └────────────┘ │                                           │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Fallback Architecture

```
FALLBACK_ARCHITECTURE=Lambda_Function_URL_Python_CockroachDB_Direct_psycopg2_only
```

If the CockroachDB Cloud Managed MCP Server introduces unacceptable
runtime authentication complexity within the available time, the fallback
replaces all MCP tool calls with direct `psycopg2` SQL queries.

- CockroachDB Tool 1 remains: **Distributed Vector Indexing** (via pgvector-compatible `VECTOR` type + `CREATE VECTOR INDEX`)
- CockroachDB Tool 2 becomes: **ccloud CLI** used for schema verification and provisioning evidence in CI (judge-visible via recorded terminal output in the demo video)
- All AWS, governance, and demo scenario decisions remain identical.
- The fallback is activated only if MCP Server auth cannot be made functional during milestone 0E.

---

## End-to-End Flow

```
OBSERVE      → incident payload received (synthetic, no real customer data)
RETRIEVE     → CockroachDB: semantic vector search over memory_events for similar
               prior incidents; transactional query for current service_state
PROPOSE      → control plane generates a bounded proposal:
               { action: "set_service_mode", target: "synthetic-svc-01",
                 from: "NORMAL", to: "SAFE", mission_id: <uuid> }
POLICY CHECK → deterministic Python policy engine evaluates the proposal
               against explicit rules; no LLM involvement at this step
HUMAN GO     → human submits an approval permit scoped to the exact proposal;
               permit is single-use, mission-bound, action-bound, expiry-aware
EXECUTE      → Lambda executes the bounded action; writes evidence to S3;
               execution is refused if no valid permit exists (FAIL_CLOSED)
PERSIST      → CockroachDB: execution_receipt written; service_state updated
READBACK     → CockroachDB: state queried and compared to expected value
PROVE        → structured response: expected_state, observed_state,
               match/mismatch, evidence S3 key, audit trail
```

---

## CockroachDB Tools

### Tool 1 — Distributed Vector Indexing

```
WHY_IT_EXISTS=
  Semantic memory retrieval: given a new incident, find the most relevant prior
  incidents and successful responses stored in CockroachDB. Pure transactional
  lookup cannot retrieve context by semantic similarity.

WHAT_THE_AGENT_DOES_WITH_IT=
  Embeddings of memory_event content are stored in a VECTOR column on the
  memory_events table. At retrieval time, the agent computes an embedding for
  the incoming incident and executes a vector similarity query (cosine or L2)
  against the CockroachDB vector index. The top-k results inform the proposal.

WHAT_THE_JUDGE_CAN_SEE=
  - The demo shows a semantic query returning a ranked list of prior incidents.
  - The STACK-FREEZE and demo video explain the vector index role.
  - The CockroachDB schema (milestone 0D) contains an explicit CREATE VECTOR INDEX.
  - Query results and latency are visible in the demo terminal output.

WHAT_EVIDENCE_PROVES_IT=
  - Schema DDL shows the VECTOR column and index.
  - Demo logs show the similarity search SQL and result rows.
  - S3 evidence bundle includes the query trace.

FAILURE_BEHAVIOR=
  If vector search is unavailable, the control plane falls back to a keyword
  match on the incident description using full-text (tsvector) search.
  The proposal is generated with a SEMANTIC_RETRIEVAL_DEGRADED warning flag.
  Execution is not blocked by retrieval degradation; execution is blocked only
  by a missing/expired Human GO permit.
```

**Official source:** https://www.cockroachlabs.com/docs/stable/vector-search

### Tool 2 — Cloud Managed MCP Server

```
WHY_IT_EXISTS=
  The CockroachDB Cloud Managed MCP Server exposes CockroachDB operations as
  structured MCP tool calls, enabling an LLM-backed agent to interact with the
  database using tool definitions rather than raw SQL strings. This makes the
  CockroachDB integration judge-visible as a first-class agentic capability.

WHAT_THE_AGENT_DOES_WITH_IT=
  During the RETRIEVE and PROPOSE steps, the Python control plane invokes MCP
  tool calls against the Managed MCP Server (authenticated via CockroachDB
  Cloud API key) to:
  - query memory_events for relevant context;
  - read current service_state;
  - write the proposal record.
  Direct psycopg2 queries handle all write-back and readback steps where
  transactional integrity is critical (execution_receipts, audit).

WHAT_THE_JUDGE_CAN_SEE=
  - MCP tool call invocations are logged in the demo terminal.
  - The control plane config references the MCP Server endpoint.
  - The demo video shows memory retrieval via MCP tool calls.

WHAT_EVIDENCE_PROVES_IT=
  - Demo logs include MCP request/response pairs.
  - Architecture diagram names the MCP Server component.

FAILURE_BEHAVIOR=
  If the Managed MCP Server is unavailable, the control plane falls back to
  direct psycopg2 queries (see Fallback Architecture above).
  This degradation is logged. Governance and execution are not affected.
  FALLBACK_TRIGGER=MCP_SERVER_UNAVAILABLE
```

**Official source:** https://www.cockroachlabs.com/docs/cockroachcloud/managed-mcp-server

### Optional Tool 3 — ccloud CLI

```
OPTIONAL=true
ROLE=Provisioning evidence and schema management in CI/demo setup

WHY_IT_EXISTS=
  ccloud CLI provides a repeatable, scriptable way to provision the CockroachDB
  Serverless cluster, create the database, and apply schema DDL. Its use is
  recorded in the demo setup and visible in the repository's setup script.

WHAT_THE_AGENT_DOES_WITH_IT=
  Not used at runtime by the control plane. Used by the demo operator to:
  - provision the cluster (milestone 0D);
  - apply schema;
  - verify cluster state in the demo video setup segment.

WHAT_THE_JUDGE_CAN_SEE=
  ccloud commands in the recorded demo setup terminal.

FAILURE_BEHAVIOR=
  No runtime impact. ccloud is a setup tool only.
```

**Official source:** https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-get-started

---

## Persistent Memory Model

CockroachDB is the sole persistent memory store. No other database is used.

### Transactional Memory

Stores structured operational state with ACID guarantees:

| Table | What It Remembers |
|---|---|
| `missions` | Active operational contexts, their status and scope |
| `proposals` | Every bounded proposal generated, with policy verdict |
| `approval_permits` | Human GO records: scope, expiry, single-use flag, consumed state |
| `service_state` | Current and historical state of managed synthetic services |
| `execution_receipts` | Tamper-evident log of every execution attempt and outcome |

### Semantic Memory

Stores embedded representations of past incidents and responses for retrieval:

| Table | What It Remembers |
|---|---|
| `memory_events` | Past incidents, responses, and observations as text + vector embedding |

### Invariants

```
VECTOR_AUTHORITY=false
MEMORY_AUTHORITY=false
LLM_AUTHORITY=false
ONLY_VALID_PERMIT_AUTHORIZES_EXECUTION=true
FAIL_CLOSED_ON_MISSING_PERMIT=true
```

---

## Conceptual Schema

Six tables. No SQL in this document — SQL is milestone 0D.

### 1. `missions`

```
PURPOSE:      Root context for an operational workstream.
IDENTITY:     mission_id (UUID)
CRITICAL:     status (ACTIVE|COMPLETED|ABORTED), scope_json, created_at, closed_at
AUTHORITY:    Proposals and permits must reference a valid active mission.
RETENTION:    Permanent — used as evidence root.
VECTOR:       No
```

### 2. `memory_events`

```
PURPOSE:      Persistent record of every significant observation, incident,
              or agent action, with an embedding for semantic retrieval.
IDENTITY:     event_id (UUID)
CRITICAL:     mission_id (FK), event_type, content_text, embedding (VECTOR),
              created_at, source
AUTHORITY:    Informs proposals only. Never authorizes.
RETENTION:    Permanent — primary semantic memory store.
VECTOR:       YES — embedding column + vector index for cosine similarity search
```

### 3. `proposals`

```
PURPOSE:      Every bounded action proposal generated by the agent,
              including the policy verdict and the triggering memory context.
IDENTITY:     proposal_id (UUID)
CRITICAL:     mission_id (FK), action_type, target, from_state, to_state,
              policy_result (APPROVED|DENIED|REQUIRES_HUMAN_GO),
              retrieved_event_ids (array), created_at
AUTHORITY:    Records the policy verdict. Does not grant authority.
RETENTION:    Permanent — evidence of what was proposed and why.
VECTOR:       No
```

### 4. `approval_permits`

```
PURPOSE:      Human GO records. Each permit is single-use, scope-bound,
              action-bound, mission-bound, and expiry-aware.
IDENTITY:     permit_id (UUID)
CRITICAL:     proposal_id (FK), mission_id (FK), action_type, target,
              from_state, to_state, granted_by, granted_at, expires_at,
              consumed (BOOLEAN), consumed_at, consumed_by_receipt_id
AUTHORITY:    THE authority record. Execution requires a valid, unconsumed,
              unexpired permit matching the exact proposed action.
RETENTION:    Permanent — primary authority evidence.
VECTOR:       No
```

### 5. `service_state`

```
PURPOSE:      Current and historical state of every managed synthetic service.
IDENTITY:     (service_id, recorded_at) composite; latest view via query
CRITICAL:     service_id, current_mode (NORMAL|SAFE|DEGRADED|LOCKED),
              previous_mode, changed_at, changed_by_receipt_id
AUTHORITY:    Records observed state. Does not grant authority.
RETENTION:    Full history retained — readback verification uses this.
VECTOR:       No
```

### 6. `execution_receipts`

```
PURPOSE:      Tamper-evident log of every execution attempt: permitted,
              denied, and error cases.
IDENTITY:     receipt_id (UUID)
CRITICAL:     permit_id (FK, nullable — null if execution was denied),
              proposal_id (FK), mission_id (FK), executed_at, outcome
              (EXECUTED|DENIED_NO_PERMIT|DENIED_EXPIRED|DENIED_REPLAY|ERROR),
              aws_request_id, s3_evidence_key, readback_state, readback_match
AUTHORITY:    Evidence only. Immutable after insertion.
RETENTION:    Permanent. Append-only.
VECTOR:       No
```

---

## AWS Services

### Primary Service 1 — AWS Lambda

```
RUNTIME=python3.12
TRIGGER=Lambda Function URL (HTTPS, no API Gateway required)
MEMORY=256 MB (sufficient for psycopg2 + MCP client + small embedding model)
TIMEOUT=30 seconds
CONCURRENCY=reserved 1 (demo; prevents parallel permit conflicts)
VPC=NONE required
  CockroachDB Serverless is reachable over public TLS on port 26257/5432.
  No VPC peering or NAT Gateway is needed.
CORS=Lambda Function URL supports CORS configuration natively
SECRETS=AWS Secrets Manager (environment variable reference; no plaintext)
```

**Why Lambda Function URL over API Gateway:**
- Lambda Function URL is free within Lambda free tier invocations.
- API Gateway HTTP API adds ~$1/million requests — unnecessary for a demo.
- No path routing needed; all control plane logic is in one function.
- Simpler deployment surface; fewer moving parts to debug.
- HTTPS is provided natively; TLS termination is handled by AWS.

### Primary Service 2 — Amazon S3

```
BUCKET_VISIBILITY=PRIVATE
PURPOSE=Evidence bundle storage
  Each execution receipt references an S3 object containing:
  - the full proposal JSON;
  - the permit record;
  - the execution log;
  - the readback result.
  S3 objects are written by the Lambda function using the execution IAM role.
  Pre-signed URLs (15-minute TTL) are returned to the caller for demo visibility.
ACCESS_MODEL=IAM role attached to Lambda; no public bucket policy
VERSIONING=enabled (evidence immutability)
COST=negligible for demo scale (< 1 MB total objects)
```

---

## Runtime Language

```
RUNTIME_LANGUAGE=Python 3.12
```

**Decision rationale:**

| Factor | Python 3.12 | Alternative |
|---|---|---|
| AWS Lambda support | Native (`python3.12` runtime) | Go, Node also available |
| CockroachDB client | `psycopg2-binary` / `psycopg3` (Postgres wire protocol) | Excellent |
| Vector/pgvector support | `pgvector` Python package; direct SQL via psycopg | Excellent |
| MCP client | `mcp` Python SDK (official) | Only Python + Node have official SDKs |
| Implementation speed | Fastest for Bob + Arthur collaboration | — |
| Dependency footprint | Small: psycopg2, mcp, boto3 (included in Lambda) | — |
| Testing | pytest; straightforward mocking of DB + AWS | — |
| IBM Bob effectiveness | Primary language for Bob's Lambda and DB guidance | — |

No alternative language offers a materially safer path given the available time.

---

## Runtime Model

```
RUNTIME_MODEL_STRATEGY=hybrid_llm_proposal_deterministic_authority
LLM_AUTHORITY=false
```

### Doctrine

```
LLM may:        propose, summarize, retrieve context, generate embeddings
LLM may NOT:    authorize, mint permits, bypass policy, modify approval_permits

MEMORY != AUTHORITY
LLM != AUTHORITY
VECTOR_MATCH != AUTHORITY
HUMAN_GO = scoped authorization (deterministic)
POLICY_ENGINE = deterministic Python evaluation
```

### Model selection

```
PRIMARY_MODEL=OpenAI text-embedding-3-small  (embeddings only)
PROPOSAL_GENERATION=deterministic rule-based Python (no LLM required for demo)
OPTIONAL_LLM_SUMMARY=OpenAI gpt-4o-mini (non-authoritative; demo only)
```

**Why not Amazon Bedrock:**
- Bedrock adds IAM complexity, model access request latency, and cost uncertainty.
- The demo's authoritative paths (policy check, permit validation, execution) are
  fully deterministic; they do not require LLM inference.
- Bedrock is not selected solely because AWS sponsors the competition.
- Bedrock remains eligible for a future milestone if the proposal generator is
  upgraded to an LLM-backed reasoning step with explicit non-authority constraints.

**Why the architecture remains functional without LLM:**
- If OpenAI is unavailable: embeddings fall back to zero-vector; vector search
  degrades to keyword match; proposal is generated by the deterministic rule engine.
- The governance path (policy check → Human GO → execution → readback) requires
  no LLM at any step.

---

## Authority Boundary

```
OBSERVE  → no authority
RETRIEVE → no authority (memory informs, never authorizes)
PROPOSE  → no authority (proposal is a request, not a grant)
POLICY CHECK → no authority (verdict is APPROVE_PENDING_HUMAN_GO or DENY)
HUMAN GO → CREATES exactly one scoped, single-use, expiry-aware permit
EXECUTE  → REQUIRES a valid permit; fails closed if none exists
READBACK → no authority (verification only)
PROVE    → no authority (evidence only)
```

### Human GO Contract

```
HUMAN_GO_REQUIRED=true for any state-changing execution
HUMAN_GO_SINGLE_USE=true
HUMAN_GO_SCOPE_BOUND=true (action_type + target + from_state + to_state)
HUMAN_GO_ACTION_BOUND=true
HUMAN_GO_MISSION_BOUND=true
HUMAN_GO_EXPIRY_AWARE=true (default TTL: 5 minutes)
HUMAN_GO_NON_REUSABLE=true (consumed flag set atomically at execution start)
HUMAN_GO_REPLAY_REJECTED=true (consumed permits cannot authorize a second execution)
```

**Rejection cases (all FAIL_CLOSED):**

| Scenario | Outcome |
|---|---|
| No permit exists | `DENIED_NO_PERMIT` — execution refused |
| Permit expired | `DENIED_EXPIRED` — execution refused |
| Permit already consumed | `DENIED_REPLAY` — execution refused |
| Permit scope mismatch | `DENIED_SCOPE_MISMATCH` — execution refused |
| Permit mission mismatch | `DENIED_MISSION_MISMATCH` — execution refused |

The system must visibly reject execution in all five cases. The demo must demonstrate
at least the `DENIED_NO_PERMIT` case before showing the approved path.

---

## Demo Scenario

```
DEMO_SCENARIO=synthetic_service_mode_transition
DEMO_ACTION=set_service_mode NORMAL→SAFE
```

**Scenario:**

1. A synthetic service `synthetic-svc-01` is in `NORMAL` mode. This state is
   stored in CockroachDB `service_state`.
2. An operational incident is injected: "High error rate detected on synthetic-svc-01."
3. CockroachDB vector search retrieves the most semantically similar prior
   incident. CockroachDB transactional query returns current service state.
4. The control plane generates a proposal:
   `{ action: set_service_mode, target: synthetic-svc-01, from: NORMAL, to: SAFE }`
5. Policy check: transition NORMAL→SAFE is allowed by policy, but requires Human GO.
6. **Without Human GO:** execution is attempted → `DENIED_NO_PERMIT`. Evidence written.
7. Human submits approval for the exact bounded proposal.
   CockroachDB `approval_permits` record created.
8. **With Human GO:** Lambda executes the state transition.
   S3 evidence bundle written. CockroachDB `execution_receipts` updated.
   `service_state` updated to `SAFE`.
9. Readback: CockroachDB queried. Expected: `SAFE`. Observed: `SAFE`. `MATCH`.
10. Terminal output shows the full evidence trail: proposal → permit → receipt →
    readback → S3 key.

**Constraints:**
- No production infrastructure.
- No real customer data.
- No financial action.
- No destructive operation.
- The synthetic service is a row in `service_state`; it has no real infrastructure.

---

## Failure Behavior

All consequential paths are FAIL_CLOSED.

| Failure | Behavior |
|---|---|
| CockroachDB unavailable | Lambda returns 503; execution not attempted; error logged |
| Vector search unavailable (index) | Degrades to keyword match; SEMANTIC_DEGRADED flag set; execution not blocked |
| LLM unavailable | Embeddings fall back to zero-vector; proposal generated by deterministic rules; execution not blocked |
| Human GO missing | `DENIED_NO_PERMIT`; execution refused; receipt written with DENIED outcome |
| Human GO expired | `DENIED_EXPIRED`; execution refused; receipt written |
| Human GO replay attempted | `DENIED_REPLAY`; consumed flag checked atomically; execution refused |
| AWS executor failure (Lambda error) | Receipt written with ERROR outcome; state not updated; caller receives 500 |
| Write succeeds but readback mismatches | Receipt records `readback_match=false`; evidence includes mismatch detail; no retry without new Human GO |
| Evidence persistence failure (S3 write fails) | Execution is rolled back or marked ERROR; no silent partial success |
| MCP Server unavailable | Falls back to direct psycopg2; governance unaffected |

---

## Security and Secrets

No secrets are created, provisioned, or committed in this milestone.

**Future secret architecture (milestone 0D+):**

| Secret | Storage | Access model |
|---|---|---|
| CockroachDB database connection string | AWS Secrets Manager | Lambda IAM role → `secretsmanager:GetSecretValue` |
| CockroachDB Cloud API key (MCP Server) | AWS Secrets Manager | Same Lambda IAM role |
| OpenAI API key | AWS Secrets Manager | Same Lambda IAM role |
| AWS region / S3 bucket name | Lambda environment variables (non-secret config) | Direct |

**Invariants:**

```
NO_SECRET_IN_GIT=true
NO_PUBLIC_S3_BUCKET=true
NO_PLAINTEXT_ENV_SECRET=true
IAM_LEAST_PRIVILEGE=true
.env.example=deferred to milestone 0D
```

---

## Cost Envelope

```
OUT_OF_POCKET_COST_TARGET=0_USD
AWS_ZERO_COST_GUARANTEE=false
COCKROACH_ZERO_COST_GUARANTEE=false
```

**AWS Free Tier (12-month or always-free):**

| Service | Free tier | Demo usage |
|---|---|---|
| AWS Lambda | 1M requests/month + 400,000 GB-seconds | < 100 invocations |
| Amazon S3 | 5 GB storage, 20K GET, 2K PUT | < 1 MB, < 50 objects |
| AWS Secrets Manager | 30-day trial per secret | 3 secrets |

Expected demo cost: **$0** within free tier. Secrets Manager is the only potential
cost if the 30-day trial has already been used (~$0.40/secret/month).

**CockroachDB:**

| Plan | Cost | Notes |
|---|---|---|
| Serverless Basic (free tier) | $0 up to 50M RUs/month + 10 GiB | Sufficient for demo |
| Serverless Standard | Pay-per-use | Not required |

Explicit teardown is required after demo to prevent ongoing charges.

---

## Judge-Visible Evidence

| Evidence item | Where visible |
|---|---|
| CockroachDB vector index creation | Schema DDL in repo + demo video |
| Semantic memory retrieval (vector query) | Demo terminal: SQL query + result rows |
| MCP tool call invocations | Demo terminal: MCP request/response logs |
| Transactional state before/after | Demo terminal: service_state query |
| DENIED_NO_PERMIT rejection | Demo terminal: execution refused output |
| Human GO permit creation | Demo terminal: permit record written to CockroachDB |
| Successful execution receipt | Demo terminal: receipt_id + outcome=EXECUTED |
| Readback match | Demo terminal: expected=SAFE observed=SAFE MATCH |
| S3 evidence bundle | Pre-signed URL returned in response; shown in demo |
| Full audit trail in CockroachDB | Demo video: query of execution_receipts |

---

## Explicitly Excluded Scope

Milestone 0C does NOT include:

- CockroachDB cluster provisioning
- CockroachDB API key creation
- AWS account provisioning
- AWS IAM resource creation
- S3 bucket creation
- Lambda function creation or deployment
- MCP server configuration
- Schema creation or SQL execution
- Application source code
- Package installation (`pip install`, `npm install`, `uv sync`)
- UI implementation
- API route implementation
- Runtime model calls or inference
- Devpost submission edits
- Video production
- `.env` or `.env.example` creation
- GitHub Actions workflows
- Branch protection rules

These are all deferred to milestone 0D (prerequisites and controlled provisioning)
and subsequent milestones, each requiring a separate Human GO.

---

## Official Sources

| # | Source | URL | Used for |
|---|---|---|---|
| 1 | CockroachDB Vector Search | https://www.cockroachlabs.com/docs/stable/vector-search | Vector indexing capability confirmation |
| 2 | CockroachDB Cloud Managed MCP Server | https://www.cockroachlabs.com/docs/cockroachcloud/managed-mcp-server | MCP Server auth model and availability |
| 3 | CockroachDB ccloud CLI | https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-get-started | ccloud CLI tool reference |
| 4 | AWS Lambda runtimes | https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html | python3.12 runtime confirmation |
| 5 | AWS Lambda Function URLs | https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html | HTTPS endpoint without API Gateway |
| 6 | AWS Lambda free tier | https://aws.amazon.com/lambda/pricing/ | Cost model |
| 7 | Amazon S3 free tier | https://aws.amazon.com/s3/pricing/ | Cost model |
| 8 | CockroachDB Serverless pricing | https://www.cockroachlabs.com/pricing/ | Free tier eligibility |
| 9 | CockroachDB × AWS Hackathon | https://cockroachdb-aws-hackathon.devpost.com | Competition rules and tool eligibility |
| 10 | MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk | Python MCP client |

---

## Gate to Implementation

This document is frozen. The architecture is decided.

The next authorized milestone is:

```
NEXT_MILESTONE=BOSAI_COCKROACHDB_AWS_0D
NEXT_MILESTONE_NAME=PREREQUISITES_AND_CONTROLLED_PROVISIONING
GATE=SEPARATE_HUMAN_GO_REQUIRED
```

Milestone 0D is authorized to:
- provision the CockroachDB Serverless cluster (ccloud CLI or Console)
- provision the AWS Lambda function shell and S3 bucket
- apply the schema DDL (SQL creation, not implemented here)
- create AWS Secrets Manager entries
- create `.env.example`

Milestone 0D is NOT authorized to implement application logic.
That requires milestone 0E with a separate Human GO.
