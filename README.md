# BOSAI Agent Memory Control Plane

## Status

**Bootstrap only — implementation not started.**

This repository was created as the dedicated hackathon workspace for the
CockroachDB × AWS Hackathon. No application code, database schemas, cloud
infrastructure, or integrations exist yet.

---

## Problem

AI agents need persistent memory across sessions and incidents, but *remembered
information must never silently become permission to act*.

Today's agentic systems either forget everything between runs (stateless) or
grant too much autonomy once context is present (unchecked execution).

BOSAI Agent Memory Control Plane closes that gap: memory informs proposals,
but authority is always bounded, deterministic, and requires Human GO before
consequential actions execute.

---

## Hackathon

**CockroachDB × AWS Hackathon — Build with Agentic Memory**

| Field | Value |
|---|---|
| Devpost | Registered |
| Project | BOSAI Agent Memory Control Plane |
| Repository | public — this repository |

---

## Core Idea

```
Operational incident
  → memory retrieval       (CockroachDB)
  → agent proposal         (bounded, scoped)
  → authority check        (BOSAI governance policy)
  → Human GO               (explicit approval gate)
  → controlled AWS action  (Lambda / S3)
  → state persistence      (CockroachDB write-back)
  → verified readback      (CockroachDB query)
  → evidence               (tamper-evident log)
```

Memory **informs** proposals. Memory never **authorises** execution.

---

## Planned Architecture

> All items below are **planned / not yet integrated**.

```
┌──────────────────────────────────────────────────────┐
│                  BOSAI Control Plane                 │
│                                                      │
│  [Incident Input]                                    │
│       │                                              │
│       ▼                                              │
│  [Memory Retrieval] ◄──── CockroachDB (vector + KV) │
│       │                                              │
│       ▼                                              │
│  [Agent Proposal Generator]                          │
│       │                                              │
│       ▼                                              │
│  [Authority Check] ──── BOSAI Governance Policy      │
│       │                                              │
│       ▼                                              │
│  [Human GO Gate] ◄──── Explicit approval required    │
│       │                                              │
│       ▼                                              │
│  [Controlled Execution] ──── AWS Lambda / S3         │
│       │                                              │
│       ▼                                              │
│  [Persistence + Readback] ──── CockroachDB           │
│       │                                              │
│       ▼                                              │
│  [Evidence Layer]                                    │
└──────────────────────────────────────────────────────┘
```

---

## Governance Model

- Memory content and vector similarity **never** directly authorize execution.
- Every consequential action requires a bounded proposal evaluated against
  explicit policy rules.
- Where policy permits, a **Human GO** gate must be cleared before execution.
- All decisions and state transitions are persisted and readable as evidence.

---

## Technology Targets

> All items below are **planned / not yet integrated**.

| Technology | Role | Status |
|---|---|---|
| CockroachDB Cloud | Persistent agent memory (KV + vector) | Planned |
| CockroachDB Managed MCP Server | Tool access for agent memory operations | Planned |
| CockroachDB Distributed Vector Indexing | Semantic memory retrieval | Planned |
| AWS Lambda | Controlled execution environment | Planned |
| Amazon S3 | Evidence and artifact storage | Planned |
| IBM Bob | AI coding assistant and bounded implementation agent | Active (bootstrap) |

---

## Development Status

| Milestone | Status |
|---|---|
| `0B` — Dedicated Repository & Workspace Bootstrap | ✅ Complete |
| `0C` — Architecture & Stack Freeze | Not started |
| `0D` — CockroachDB Schema & Memory Layer | Not started |
| `0E` — Agent Core & Governance Engine | Not started |
| `0F` — AWS Integration | Not started |
| `0G` — End-to-End Demo & Evidence | Not started |

---

## Provenance

- BOSAI name and governance philosophy predate this hackathon.
- All implementation in this repository is new and created specifically for
  the CockroachDB × AWS Hackathon.
- No source code is copied from protected BOSAI repositories.
- See [`docs/PROVENANCE.md`](docs/PROVENANCE.md) for the full declaration.

---

## License

[MIT License](LICENSE) — Copyright (c) 2026 Arthur Franck
