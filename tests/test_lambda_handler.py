from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from bosai_memory.domain import (
    EventType,
    MemoryEvent,
    Mission,
    MissionStatus,
    OperationalVector,
    ServiceMode,
    ServiceState,
    now_utc,
)
from bosai_memory.persistence import MemoryRepository
import bosai_memory.lambda_handler as lh


class FakeS3:
    def __init__(self) -> None:
        self.put_calls = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        return {"ETag": '"fake"'}


class FakeContext:
    aws_request_id = "0f-test-request-id"


@pytest.fixture
def read_repo():
    repo = Mock(spec=MemoryRepository)

    state = ServiceState(
        service_id="synthetic-svc-01",
        mode=ServiceMode.NORMAL,
        version=1,
        updated_at=now_utc(),
    )

    alpha_mission = Mission(
        mission_id="00000000-0000-0000-0000-000000000001",
        incident_key="INCIDENT-2024-ALPHA",
        status=MissionStatus.CLOSED,
        observed_at=now_utc(),
        context_json={},
    )
    beta_mission = Mission(
        mission_id="00000000-0000-0000-0000-000000000002",
        incident_key="INCIDENT-2024-BETA",
        status=MissionStatus.CLOSED,
        observed_at=now_utc(),
        context_json={},
    )

    alpha = MemoryEvent(
        memory_event_id="00000000-0000-0000-0001-000000000001",
        mission_id=alpha_mission.mission_id,
        event_type=EventType.INCIDENT,
        content="alpha",
        operational_vector=OperationalVector(0.75, 0.65, 0.55),
        created_at=now_utc(),
    )
    beta = MemoryEvent(
        memory_event_id="00000000-0000-0000-0001-000000000002",
        mission_id=beta_mission.mission_id,
        event_type=EventType.INCIDENT,
        content="beta",
        operational_vector=OperationalVector(0.1, 0.2, 0.9),
        created_at=now_utc(),
    )

    repo.get_service_state.return_value = state
    repo.get_nearest_memory_events.return_value = [alpha, beta]

    missions = {
        alpha_mission.mission_id: alpha_mission,
        beta_mission.mission_id: beta_mission,
    }
    repo.get_mission.side_effect = lambda mission_id: missions.get(mission_id)

    return repo


def test_readback_returns_expected_service_state(read_repo):
    s3 = FakeS3()
    result = lh.run_readback(
        read_repo,
        s3,
        "test-bucket",
        request_id="req-1",
    )

    assert result["service_state"] == {
        "service_id": "synthetic-svc-01",
        "mode": "NORMAL",
        "version": 1,
    }


def test_readback_returns_alpha_then_beta(read_repo):
    s3 = FakeS3()
    result = lh.run_readback(
        read_repo,
        s3,
        "test-bucket",
        request_id="req-2",
    )

    assert [m["incident_key"] for m in result["nearest_memory"]] == [
        "INCIDENT-2024-ALPHA",
        "INCIDENT-2024-BETA",
    ]


def test_readback_authority_flags_are_bounded(read_repo):
    result = lh.run_readback(
        read_repo,
        FakeS3(),
        "test-bucket",
        request_id="req-3",
    )

    assert result["READBACK_ONLY"] is True
    assert result["COCKROACHDB_MUTATION_PERFORMED"] is False
    assert result["HUMAN_GO_EXECUTION_PERFORMED"] is False
    assert result["PERMIT_CREATED"] is False
    assert result["PERMIT_CONSUMED"] is False
    assert result["MEMORY_AUTHORITY"] is False
    assert result["VECTOR_AUTHORITY"] is False
    assert result["LLM_AUTHORITY"] is False


def test_readback_invokes_no_repository_write_method(read_repo):
    lh.run_readback(
        read_repo,
        FakeS3(),
        "test-bucket",
        request_id="req-4",
    )

    read_repo.save_mission.assert_not_called()
    read_repo.save_memory_event.assert_not_called()
    read_repo.save_proposal.assert_not_called()
    read_repo.save_permit.assert_not_called()
    read_repo.update_permit.assert_not_called()
    read_repo.update_service_state.assert_not_called()
    read_repo.save_receipt.assert_not_called()


def test_evidence_payload_contains_no_database_url_or_credentials(read_repo):
    s3 = FakeS3()
    result = lh.run_readback(
        read_repo,
        s3,
        "test-bucket",
        request_id="req-5",
    )

    blob = json.dumps(result).upper()
    assert "DATABASE_URL" not in blob
    assert "AWS_SECRET_ACCESS_KEY" not in blob
    assert "AWS_SESSION_TOKEN" not in blob
    assert "PASSWORD" not in blob


def test_s3_evidence_key_is_bounded(read_repo):
    s3 = FakeS3()
    result = lh.run_readback(
        read_repo,
        s3,
        "test-bucket",
        request_id="req-6",
    )

    assert result["evidence_key"] == "evidence/0f/req-6.json"
    assert len(s3.put_calls) == 1
    assert s3.put_calls[0]["Bucket"] == "test-bucket"
    assert s3.put_calls[0]["Key"] == "evidence/0f/req-6.json"
    assert s3.put_calls[0]["ServerSideEncryption"] == "AES256"


def test_unexpected_action_fails_closed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "not-used")
    monkeypatch.setenv("EVIDENCE_BUCKET", "not-used")

    response = lh.lambda_handler({"action": "execute"}, FakeContext())
    body = json.loads(response["body"])

    assert response["statusCode"] == 400
    assert body["status"] == "DENIED"
    assert body["error_code"] == "ACTION_NOT_ALLOWED"
    assert body["READBACK_ONLY"] is True


def test_missing_database_url_fails_closed(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("EVIDENCE_BUCKET", "test-bucket")

    response = lh.lambda_handler({"action": "readback"}, FakeContext())
    body = json.loads(response["body"])

    assert response["statusCode"] == 500
    assert body["error_code"] == "DATABASE_URL_REQUIRED"


def test_missing_evidence_bucket_fails_closed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "not-used")
    monkeypatch.delenv("EVIDENCE_BUCKET", raising=False)

    response = lh.lambda_handler({"action": "readback"}, FakeContext())
    body = json.loads(response["body"])

    assert response["statusCode"] == 500
    assert body["error_code"] == "EVIDENCE_BUCKET_REQUIRED"


def test_unexpected_service_state_fails_closed(read_repo):
    read_repo.get_service_state.return_value = ServiceState(
        service_id="synthetic-svc-01",
        mode=ServiceMode.SAFE,
        version=2,
        updated_at=now_utc(),
    )

    with pytest.raises(lh.BoundedReadbackError) as exc:
        lh.run_readback(
            read_repo,
            FakeS3(),
            "test-bucket",
            request_id="req-10",
        )

    assert exc.value.code == "SERVICE_STATE_UNEXPECTED"


def test_wrong_vector_order_fails_closed(read_repo):
    events = read_repo.get_nearest_memory_events.return_value
    read_repo.get_nearest_memory_events.return_value = list(reversed(events))

    with pytest.raises(lh.BoundedReadbackError) as exc:
        lh.run_readback(
            read_repo,
            FakeS3(),
            "test-bucket",
            request_id="req-11",
        )

    assert exc.value.code == "VECTOR_ORDER_MISMATCH"


def test_full_handler_accepts_function_url_json_body(
    monkeypatch,
    read_repo,
):
    s3 = FakeS3()

    monkeypatch.setenv("DATABASE_URL", "secret-not-emitted")
    monkeypatch.setenv("EVIDENCE_BUCKET", "test-bucket")
    monkeypatch.setattr(lh, "_build_repo", lambda database_url: read_repo)
    monkeypatch.setattr(lh, "_build_s3_client", lambda: s3)

    response = lh.lambda_handler(
        {"body": '{"action":"readback"}'},
        FakeContext(),
    )
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["status"] == "PASS"
    assert body["service_state"]["mode"] == "NORMAL"
    assert body["nearest_memory"][0]["incident_key"] == "INCIDENT-2024-ALPHA"
    assert body["READBACK_ONLY"] is True
    assert len(s3.put_calls) == 1
