from pathlib import Path

import httpx
import pytest

from runbookiq.app import create_local_app
from runbookiq.evaluation.benchmark import CRASHLOOP_SOURCE


async def _upload_and_find_source_id(content: bytes) -> str:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": "platform"},
            files={"file": ("crashloopbackoff.md", content, "text/markdown")},
        )
        answered = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": "platform",
                "question": "Which command shows logs from the previous crashed container?",
            },
        )

    assert uploaded.status_code == 202
    assert uploaded.json()["status"] == "completed"
    assert answered.status_code == 200
    return answered.json()["citations"][0]["source_id"]


@pytest.mark.asyncio
async def test_markdown_source_identity_is_stable_across_newline_styles() -> None:
    project_root = Path(__file__).resolve().parents[2]
    lf_content = (
        project_root / "examples" / "runbooks" / "crashloopbackoff.md"
    ).read_bytes()
    assert b"\r\n" not in lf_content
    crlf_content = lf_content.replace(b"\n", b"\r\n")

    lf_source_id = await _upload_and_find_source_id(lf_content)
    crlf_source_id = await _upload_and_find_source_id(crlf_content)

    assert lf_source_id == CRASHLOOP_SOURCE
    assert crlf_source_id == CRASHLOOP_SOURCE


@pytest.mark.asyncio
async def test_markdown_heading_is_preserved_from_upload_to_citation() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)
    document = b"""# Payments on Kubernetes

## CrashLoopBackOff after configuration rollout

Run `kubectl logs payment-api --previous` first. Compare the mounted ConfigMap
and Secret values with the previous ReplicaSet. Check liveness probe paths.

## Image pull failures

Inspect imagePullSecrets and registry credentials.
"""

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": "platform"},
            files={"file": ("payments.md", document, "text/markdown")},
        )
        answered = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": "platform",
                "question": "What should I inspect after a ConfigMap rollout causes CrashLoopBackOff?",
            },
        )

    assert uploaded.status_code == 202
    assert uploaded.json()["status"] == "completed"
    assert uploaded.json()["chunks_created"] >= 2
    assert answered.status_code == 200
    payload = answered.json()
    assert payload["citations"][0]["title"] == "Payments on Kubernetes"
    assert payload["citations"][0]["section_path"] == (
        "Payments on Kubernetes / CrashLoopBackOff after configuration rollout"
    )
    assert "kubectl logs payment-api --previous" in payload["citations"][0]["excerpt"]
    assert payload["answer"].endswith("[1]")
