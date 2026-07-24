from dataclasses import dataclass

import httpx
import pytest

from runbookiq.app import create_app
from runbookiq.domain.models import IngestionJob


@dataclass
class RecordingIngestion:
    submitted_filename: str | None = None

    async def submit(
        self,
        *,
        knowledge_base_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> IngestionJob:
        assert knowledge_base_id == "platform"
        assert content_type == "text/markdown"
        assert content == b"# CrashLoopBackOff\nInspect container logs."
        self.submitted_filename = filename
        return IngestionJob(
            id="job-001",
            knowledge_base_id="platform",
            filename=filename,
            status="queued",
            progress=0,
        )

    async def get_job(self, job_id: str) -> IngestionJob:
        assert job_id == "job-001"
        return IngestionJob(
            id="job-001",
            knowledge_base_id="platform",
            filename=self.submitted_filename or "runbook.md",
            status="completed",
            progress=100,
            chunks_created=3,
        )


@pytest.mark.asyncio
async def test_uploaded_runbook_becomes_an_observable_ingestion_job() -> None:
    ingestion = RecordingIngestion()
    app = create_app(ingestion=ingestion)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        submitted = await client.post(
            "/api/documents",
            data={"knowledge_base_id": "platform"},
            files={
                "file": (
                    "runbook.md",
                    b"# CrashLoopBackOff\nInspect container logs.",
                    "text/markdown",
                )
            },
        )
        observed = await client.get("/api/ingestion/jobs/job-001")

    assert submitted.status_code == 202
    assert submitted.json() == {
        "id": "job-001",
        "knowledge_base_id": "platform",
        "filename": "runbook.md",
        "status": "queued",
        "progress": 0,
        "chunks_created": 0,
        "error": None,
    }
    assert observed.status_code == 200
    assert observed.json()["status"] == "completed"
    assert observed.json()["chunks_created"] == 3

