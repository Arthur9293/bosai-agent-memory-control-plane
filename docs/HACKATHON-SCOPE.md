# Hackathon Scope

## Event

**CockroachDB × AWS Hackathon — Build with Agentic Memory**

| Field | Value |
|---|---|
| Devpost Registration | PASS |
| Project Name | BOSAI Agent Memory Control Plane |
| Repository | Arthur9293/bosai-agent-memory-control-plane (public) |

---

## Core Problem

AI agents need persistent memory, but remembered information must not silently
become permission to act.

Agents operating on operational incidents retrieve context from prior runs.
Without a governed authority layer, that retrieved context can implicitly
authorize destructive or irreversible actions. BOSAI introduces a deterministic
bounded authority model that separates memory retrieval from execution
permission.

---

## Required Vertical Slice

The hackathon demo must demonstrate a complete, end-to-end vertical slice:

```
Operational incident
  → memory retrieval       (CockroachDB persistent agent memory)
  → agent proposal         (scoped, bounded action recommendation)
  → authority check        (BOSAI governance policy evaluation)
  → Human GO               (explicit human approval gate)
  → controlled AWS action  (Lambda function execution or S3 write)
  → persistence            (CockroachDB write-back of outcome)
  → verified readback      (CockroachDB query confirming state)
  → evidence               (tamper-evident log entry)
```

No step may be skipped or simulated in the final submission.

---

## Hackathon Constraints

- **Newly created project**: this repository did not exist before the hackathon.
  All implementation is new.
- **CockroachDB as persistent memory**: CockroachDB is the primary memory
  layer. No substitute persistence technology.
- **At least two CockroachDB tools**: the implementation must use at minimum
  two distinct CockroachDB capabilities (e.g., relational tables + vector
  indexing, or CockroachDB MCP server tools).
- **At least one AWS service**: the controlled execution step must use at
  least one AWS service (Lambda and/or S3 are the current targets).
- **Public open-source repository**: this repository is public. MIT licensed.
- **Functional demo**: the vertical slice above must execute end-to-end and
  produce observable evidence.
- **Video under 3 minutes**: a demo video of 3 minutes or less is required
  for submission.

---

## Out of Scope for This Hackathon

- Modifying any existing BOSAI repository.
- Persistent production deployment beyond the demo.
- General-purpose agent orchestration framework.
- Multi-tenant or multi-user authority management.
