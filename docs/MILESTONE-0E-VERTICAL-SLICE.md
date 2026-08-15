# Milestone 0E — Memory Schema and Governed Vertical Slice

**Workstream:** BOSAI_COCKROACHDB_AWS  
**Milestone ID:** BOSAI_COCKROACHDB_AWS_0E  
**Milestone Name:** MEMORY_SCHEMA_AND_GOVERNED_VERTICAL_SLICE  
**Branch:** `milestone/bosai-cockroachdb-aws-0e-memory-schema-vertical-slice`  
**Base SHA:** `b652508e336ea8721ce852228de9765e63441d76`  
**Dependency:** PR #3 (0D Prerequisites)  
**Execution Mode:** CONTROLLED_IMPLEMENTATION  

---

## 1. Schema Status

| File | Status |
|---|---|
| `schema/001_init.sql` | ✅ Generated |
| `schema/002_seed_demo.sql` | ✅ Generated |

### Tables Defined (exactly 6)

| # | Table | Purpose |
|---|---|---|
| 1 | `missions` | Active/historical incident records |
| 2 | `memory_events` | Operational memory with VECTOR(3) |
| 3 | `proposals` | Exact proposed state transitions |
| 4 | `approval_permits` | Single-use scoped human GO permits |
| 5 | `service_state` | Authoritative service mode |
| 6 | `execution_receipts` | Immutable audit log (denied + executed) |

No seventh application table. No separate `memory_vectors` table.

### Vector Index

- Column: `memory_events.operational_vector VECTOR(3)`
- Index: `CREATE VECTOR INDEX idx_memory_events_op_vector ON memory_events (operational_vector)`
- Syntax: CockroachDB native vector index (partition-tree, not pgvector IVF)
- No cluster setting changes required

### Vector Semantics (VECTOR(3))

| Dimension | Semantic |
|---|---|
| `[0]` | Normalised latency pressure (0.0–1.0) |
| `[1]` | Normalised error pressure (0.0–1.0) |
| `[2]` | Dependency-risk pressure (0.0–1.0) |

This is a **deterministic operational similarity vector**.  
It is **not authorisation**. `VECTOR_AUTHORITY=false`.

---

## 2. Human SQL Application Status

**PENDING HUMAN ACTION** — Schema has not yet been applied to the live cluster.

### Required Action

```
HUMAN_ACTION_REQUIRED=Apply schema/001_init.sql and schema/002_seed_demo.sql
  in CockroachDB Cloud SQL Shell against bosai_agent_memory
EXPECTED_RESULT=6 tables + vector index + synthetic seed created successfully
DO_NOT_SHARE=SQL password, connection string, OAuth tokens
RESUME_PROMPT=0E CockroachDB schema and seed applied successfully.
  Continue 0E from live schema verification.
```

**Cluster:** `bosai-memory-hack` (AWS `eu-central-1`, CockroachDB v26.2.5)  
**Database:** `bosai_agent_memory`  
**SQL Shell:** CockroachDB Cloud Console → SQL Shell

---

## 3. Authority Invariants

| Invariant | Value |
|---|---|
| `MEMORY_AUTHORITY` | `false` |
| `VECTOR_AUTHORITY` | `false` |
| `LLM_AUTHORITY` | `false` |
| `POLICY_ENGINE` | `deterministic` |
| `HUMAN_GO_REQUIRED` | `true` |
| `PERMIT_SINGLE_USE` | `true` |
| `PERMIT_SCOPE_BOUND` | `true` |
| `PERMIT_MISSION_BOUND` | `true` |
| `PERMIT_EXPIRY_AWARE` | `true` |
| `PERMIT_REPLAYABLE` | `false` |
| `READBACK_REQUIRED` | `true` |
| `EVIDENCE_REQUIRED` | `true` |
| `FAIL_CLOSED` | `true` |

A vector match **may influence** a proposal. It **may never authorize** execution.

---

## 4. Python Implementation

### Package Structure

```
pyproject.toml
src/bosai_memory/
    __init__.py
    domain.py         — enums, value objects, entities, scope hash
    policy.py         — deterministic policy gate
    permits.py        — permit issuance and atomic consumption
    persistence.py    — abstract interface + InMemoryRepository + CockroachDBRepository
    memory.py         — vector similarity retrieval
    service.py        — state transitions + readback verification
    evidence.py       — execution receipt building
    handler.py        — governed vertical slice orchestrator
tests/
    conftest.py
    test_domain.py
    test_policy_gate.py
    test_memory_retrieval.py
    test_vertical_slice.py
```

### Dependencies (minimal)

| Package | Purpose |
|---|---|
| `psycopg[binary]>=3.1` | CockroachDB/PostgreSQL wire protocol |
| `boto3>=1.34` | AWS S3 evidence upload (0F) |
| `pytest>=8.0` | Test runner |

No LLM SDK. No OpenAI. No Bedrock. No LangChain. No agent framework.

### Domain Primitives Implemented

| Function | Location | Description |
|---|---|---|
| `observe_incident()` | `handler.py` | Record new mission |
| `retrieve_memory_for_incident()` | `handler.py` | Vector similarity retrieval |
| `build_proposal()` | `handler.py` | Build + persist proposed transition |
| `validate_permit_for_proposal()` | `policy.py` | Deterministic policy gate |
| `issue_permit()` | `permits.py` | Issue scoped human GO permit |
| `consume_permit()` | `permits.py` | Atomic single-use consumption |
| `attempt_execution()` | `handler.py` | Full governed execution flow |
| `execute_transition()` | `service.py` | State transition |
| `verify_readback()` | `service.py` | Post-transition verification |
| `build_evidence_receipt()` | `evidence.py` | Immutable receipt record |

### Policy Denials Enforced

| Denial Code | Trigger |
|---|---|
| `DENIED_NO_PERMIT` | No permit presented |
| `DENIED_EXPIRED_PERMIT` | Permit past `expires_at` |
| `DENIED_REPLAYED_PERMIT` | Permit already `CONSUMED` |
| `DENIED_SCOPE_MISMATCH` | `scope_hash` does not match |
| `DENIED_MISSION_MISMATCH` | Permit mission ≠ proposal mission |
| `DENIED_STATE_MISMATCH` | Current mode ≠ `from_state` |

No denied action may mutate `service_state`. Every denial produces an execution receipt.

---

## 5. Test Results

**Runtime:** Python 3.14 (≥3.12)  
**Test runner:** pytest 9.1.1  
**All tests deterministic. No external connections required.**

```
23 passed in 0.06s
```

| Test | Coverage | Result |
|---|---|---|
| `TEST_01` | No permit → denied | ✅ PASS |
| `TEST_02` | Expired permit → denied | ✅ PASS |
| `TEST_03` | Scope mismatch → denied | ✅ PASS |
| `TEST_04` | Mission mismatch → denied | ✅ PASS |
| `TEST_05` | Valid permit → NORMAL→SAFE | ✅ PASS |
| `TEST_06` | Permit consumed once | ✅ PASS |
| `TEST_07` | Replay → denied | ✅ PASS |
| `TEST_08` | Readback match → verified | ✅ PASS |
| `TEST_09` | Readback mismatch → fail closed | ✅ PASS |
| `TEST_10` | Nearest operational memory selected deterministically | ✅ PASS |
| Additional | Domain vector validation, scope hash, state mismatch | ✅ PASS (13 more) |

---

## 6. AWS Resources Created

### S3 Evidence Bucket

| Property | Value |
|---|---|
| **Bucket Name** | `bosai-agent-memory-evidence-8da8a2e5` |
| **Region** | `eu-central-1` |
| **Block Public Access** | `true` (all 4 flags) |
| **Versioning** | `Enabled` |
| **Default Encryption** | SSE-S3 (AES256) |
| **Bucket Policy** | None (no public policy) |
| **Lifecycle Rule** | `evidence/` prefix → expire after **30 days** |
| **Public ACL** | `false` |

No account identifiers published. No objects uploaded in 0E.

### IAM Lambda Execution Role

| Property | Value |
|---|---|
| **Role Name** | `bosai-agent-memory-lambda-role` |
| **Trust Principal** | `lambda.amazonaws.com` only |
| **User Access** | None |
| **Console Login** | None |
| **Static Access Keys** | None |
| **Inline Policy** | `bosai-memory-lambda-execution-policy` |
| **CloudWatch Logs** | `arn:aws:logs:eu-central-1:***:log-group:/aws/lambda/bosai-*:*` |
| **S3 Actions** | `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` |
| **S3 Scope** | `bosai-agent-memory-evidence-8da8a2e5` only |
| **Attached Managed Policies** | None |
| **Admin Policy** | `false` |

---

## 7. MCP Status

| Property | Value |
|---|---|
| `MCP_STATUS` | `PASS_PRIMARY` |
| `MCP_PERMISSION_MODE` | `READ_ONLY` |
| `MCP_WRITE_PERMISSION_GRANTED` | `false` |
| `MCP_WRITE_ATTEMPTED` | `false` |

CockroachDB MCP server remains read-only throughout 0E.

---

## 8. Lambda Boundary

Explicit 0E boundary:

| Property | Value |
|---|---|
| `LAMBDA_CREATED` | `false` |
| `FUNCTION_URL_CREATED` | `false` |
| `PUBLIC_ENDPOINT_CREATED` | `false` |
| `DEPLOYMENT_PERFORMED` | `false` |

Lambda deployment is deferred to **Milestone 0F**.

---

## 9. LLM Boundary

| Call | Status |
|---|---|
| `LLM_CALLED` | `false` |
| `OPENAI_CALLED` | `false` |
| `BEDROCK_CALLED` | `false` |
| LangChain imported | `false` |
| Agent framework | `false` |

All logic is deterministic Python. No LLM dependency in the authority core.

---

## 10. Secrets and Security

| Check | Status |
|---|---|
| Secret scan (AWS keys, tokens, passwords) | ✅ PASS |
| `git diff --check` | ✅ PASS |
| `.bob/` in `.gitignore` | ✅ CONFIRMED |
| Real `.env` committed | `false` |
| SQL password in any file | `false` |
| Connection string with credentials | `false` |

---

## 11. Vertical Slice Flow Proven

```
OBSERVE                     → observe_incident()
RETRIEVE MEMORY             → retrieve_memory_for_incident() [cosine similarity]
PROPOSE                     → build_proposal()
POLICY CHECK                → validate_permit_for_proposal()
DENY WITHOUT PERMIT         → DENIED_NO_PERMIT (receipt persisted, no state mutation)
HUMAN GO PERMIT             → issue_permit() [simulated in tests]
EXECUTE SYNTHETIC TRANSITION → attempt_execution() → NORMAL → SAFE
READBACK                    → verify_readback()
EVIDENCE RECEIPT            → build_evidence_receipt()
REJECT PERMIT REPLAY        → DENIED_REPLAYED_PERMIT (state unchanged)
```

**Synthetic action:** `SERVICE=synthetic-svc-01`, `FROM_STATE=NORMAL`, `TO_STATE=SAFE`

---

## 12. Next Gate

```
NEXT_REQUIRED_GATE=SEPARATE_HUMAN_GO_TO_BOSAI_COCKROACHDB_AWS_0F_LAMBDA_DEPLOYMENT_AND_LIVE_READBACK
STOPPED_BEFORE_0F=true
```

0F scope (not authorized by this milestone):
- Deploy Python package as AWS Lambda
- Create Function URL
- Perform live AWS readback
- Upload evidence to S3

**0F requires a separate explicit Human GO.**
