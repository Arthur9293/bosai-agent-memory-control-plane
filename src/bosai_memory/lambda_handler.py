"""
BOSAI 0F AWS Lambda entrypoint.

Milestone boundary:
- READBACK_ONLY=true
- CockroachDB reads only
- no proposal / permit / service-state mutation
- no governed execution
- S3 evidence write only
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from .domain import OperationalVector
from .persistence import CockroachDBRepository


MILESTONE = "BOSAI_COCKROACHDB_AWS_0F"
SERVICE_ID = "synthetic-svc-01"
TARGET_VECTOR = OperationalVector(0.8, 0.7, 0.6)
EXPECTED_INCIDENT_ORDER = (
    "INCIDENT-2024-ALPHA",
    "INCIDENT-2024-BETA",
)


class BoundedReadbackError(RuntimeError):
    """Fail-closed error with a non-secret bounded error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _authority_flags() -> dict[str, bool]:
    return {
        "READBACK_ONLY": True,
        "COCKROACHDB_MUTATION_PERFORMED": False,
        "HUMAN_GO_EXECUTION_PERFORMED": False,
        "PERMIT_CREATED": False,
        "PERMIT_CONSUMED": False,
        "REAL_INFRASTRUCTURE_MUTATION": False,
        "MEMORY_AUTHORITY": False,
        "VECTOR_AUTHORITY": False,
        "LLM_AUTHORITY": False,
        "OPENAI_CALLED": False,
        "BEDROCK_CALLED": False,
    }


def _response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, sort_keys=True, separators=(",", ":")),
    }


def _parse_action(event: Any) -> str | None:
    if not isinstance(event, dict):
        return None

    if isinstance(event.get("action"), str):
        return event["action"]

    body = event.get("body")
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
        except (TypeError, ValueError):
            return None
        if isinstance(parsed, dict) and isinstance(parsed.get("action"), str):
            return parsed["action"]

    if isinstance(body, dict) and isinstance(body.get("action"), str):
        return body["action"]

    return None


def _request_id(context: Any) -> str:
    value = getattr(context, "aws_request_id", None)
    return str(value) if value else str(uuid.uuid4())


def _build_repo(database_url: str) -> CockroachDBRepository:
    return CockroachDBRepository(database_url)


def _build_s3_client() -> Any:
    import boto3

    return boto3.client("s3")


def run_readback(
    repo: Any,
    s3_client: Any,
    bucket: str,
    *,
    request_id: str,
) -> dict[str, Any]:
    """
    Execute the bounded 0F readback.

    This function invokes read methods only on CockroachDBRepository.
    The sole durable write is the evidence object in S3.
    """

    state = repo.get_service_state(SERVICE_ID)
    if state is None:
        raise BoundedReadbackError("SERVICE_STATE_NOT_FOUND")

    if state.mode.value != "NORMAL" or state.version != 1:
        raise BoundedReadbackError("SERVICE_STATE_UNEXPECTED")

    events = repo.get_nearest_memory_events(TARGET_VECTOR, limit=2)
    if len(events) != 2:
        raise BoundedReadbackError("VECTOR_RESULT_COUNT_MISMATCH")

    nearest_memory: list[dict[str, Any]] = []

    for rank, memory_event in enumerate(events, start=1):
        mission = repo.get_mission(memory_event.mission_id)
        if mission is None:
            raise BoundedReadbackError("MEMORY_MISSION_NOT_FOUND")

        nearest_memory.append(
            {
                "rank": rank,
                "incident_key": mission.incident_key,
                "memory_event_id": memory_event.memory_event_id,
                "mission_id": memory_event.mission_id,
                "operational_vector": memory_event.operational_vector.to_list(),
            }
        )

    actual_order = tuple(item["incident_key"] for item in nearest_memory)
    if actual_order != EXPECTED_INCIDENT_ORDER:
        raise BoundedReadbackError("VECTOR_ORDER_MISMATCH")

    evidence_key = f"evidence/0f/{request_id}.json"

    evidence: dict[str, Any] = {
        "milestone": MILESTONE,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "lambda_request_id": request_id,
        "service_state": {
            "service_id": state.service_id,
            "mode": state.mode.value,
            "version": state.version,
        },
        "vector_target": TARGET_VECTOR.to_list(),
        "nearest_memory": nearest_memory,
        "readback_status": "PASS",
        "evidence_key": evidence_key,
        **_authority_flags(),
    }

    serialized = json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    s3_client.put_object(
        Bucket=bucket,
        Key=evidence_key,
        Body=serialized,
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )

    return evidence


def lambda_handler(event: Any, context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler.

    Supported operation:
        {"action": "readback"}

    All other operations fail closed.
    """

    action = _parse_action(event)

    if action != "readback":
        return _response(
            400,
            {
                "status": "DENIED",
                "error_code": "ACTION_NOT_ALLOWED",
                **_authority_flags(),
            },
        )

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return _response(
            500,
            {
                "status": "FAIL_CLOSED",
                "error_code": "DATABASE_URL_REQUIRED",
                **_authority_flags(),
            },
        )

    bucket = os.environ.get("EVIDENCE_BUCKET")
    if not bucket:
        return _response(
            500,
            {
                "status": "FAIL_CLOSED",
                "error_code": "EVIDENCE_BUCKET_REQUIRED",
                **_authority_flags(),
            },
        )

    try:
        repo = _build_repo(database_url)
        s3_client = _build_s3_client()

        evidence = run_readback(
            repo,
            s3_client,
            bucket,
            request_id=_request_id(context),
        )

        return _response(
            200,
            {
                "status": "PASS",
                **evidence,
            },
        )

    except BoundedReadbackError as exc:
        return _response(
            409,
            {
                "status": "FAIL_CLOSED",
                "error_code": exc.code,
                **_authority_flags(),
            },
        )

    except Exception:
        # Deliberately do not expose raw exception strings: connection errors
        # can contain hostnames or credentials.
        return _response(
            500,
            {
                "status": "FAIL_CLOSED",
                "error_code": "READBACK_FAILED",
                **_authority_flags(),
            },
        )
