import httpx
import pytest

from runbookiq.app import create_local_app


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

