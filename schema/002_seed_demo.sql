-- =============================================================================
-- BOSAI Agent Memory Control Plane — Schema 002 Seed Demo Data
-- Milestone: BOSAI_COCKROACHDB_AWS_0E
-- Database:  bosai_agent_memory
--
-- Synthetic hackathon fixtures only. No customer or production data.
-- Idempotent: uses INSERT ... ON CONFLICT DO NOTHING where possible.
--
-- Operational vector semantics (VECTOR(3)):
--   dimension_1 = normalised latency pressure   [0.0 – 1.0]
--   dimension_2 = normalised error pressure     [0.0 – 1.0]
--   dimension_3 = dependency-risk pressure      [0.0 – 1.0]
--
-- Target incident (the new mission we are about to govern):
--   [0.8, 0.7, 0.6]   — high latency + high errors + moderate dependency risk
--
-- Past incident A (INCIDENT-2024-ALPHA) — cosine-similar, close neighbour:
--   [0.75, 0.65, 0.55] — very similar operational signature → RECOVERY action known
--
-- Past incident B (INCIDENT-2024-BETA) — dissimilar control:
--   [0.1,  0.2,  0.9]  — low latency/error, high dependency risk → different cause
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Seed: synthetic-svc-01 in NORMAL mode
-- ---------------------------------------------------------------------------
INSERT INTO service_state (service_id, mode, version, updated_at)
VALUES ('synthetic-svc-01', 'NORMAL', 1, now())
ON CONFLICT (service_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Seed: two prior missions (historical incidents)
-- ---------------------------------------------------------------------------
INSERT INTO missions (mission_id, incident_key, status, observed_at, context_json)
VALUES
    (
        '00000000-0000-0000-0000-000000000001',
        'INCIDENT-2024-ALPHA',
        'CLOSED',
        now() - INTERVAL '72h',
        '{"severity":"HIGH","service":"synthetic-svc-01","resolution":"SAFE_MODE"}'
    ),
    (
        '00000000-0000-0000-0000-000000000002',
        'INCIDENT-2024-BETA',
        'CLOSED',
        now() - INTERVAL '48h',
        '{"severity":"MEDIUM","service":"synthetic-svc-03","resolution":"RESTART"}'
    )
ON CONFLICT (mission_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Seed: memory events with operational vectors
-- ALPHA event is the close neighbour (high latency + high errors).
-- BETA event is the dissimilar control (low latency/error, high dep-risk).
-- ---------------------------------------------------------------------------
INSERT INTO memory_events
    (memory_event_id, mission_id, event_type, content, operational_vector, created_at)
VALUES
    (
        '00000000-0000-0000-0001-000000000001',
        '00000000-0000-0000-0000-000000000001',
        'INCIDENT',
        'synthetic-svc-01 entered high-latency / high-error state. Recovered via SAFE mode transition after human GO permit.',
        '[0.75, 0.65, 0.55]',
        now() - INTERVAL '72h'
    ),
    (
        '00000000-0000-0000-0001-000000000002',
        '00000000-0000-0000-0000-000000000002',
        'INCIDENT',
        'synthetic-svc-03 experienced dependency cascade failure. Low latency, low errors, high dependency risk. Resolved via rolling restart.',
        '[0.1, 0.2, 0.9]',
        now() - INTERVAL '48h'
    )
ON CONFLICT (memory_event_id) DO NOTHING;
