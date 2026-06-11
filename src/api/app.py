"""FastAPI application: submit a research job, poll for the brief.

Two execution modes, chosen by whether ``STATE_MACHINE_ARN`` is configured:

* **async (production)** — submit reserves a daily slot, writes a PENDING job,
  and kicks off the Step Functions execution; the client polls ``GET /jobs/{id}``.
* **sync (local/MVP)** — with no state machine ARN, the pipeline runs in-process
  before responding. Same agents, same output, simpler to run on a laptop.
"""
from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from core.config import CONFIG
from core.deps import get_repo
from core.models import Job, JobStatus, SubmitRequest
from core.pipeline import run_pipeline
from core.repo import DailyCapReached

app = FastAPI(
    title="scout",
    summary="Serverless multi-agent research pipeline on AWS",
    version="0.1.0",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs", status_code=202)
def submit(req: SubmitRequest) -> JSONResponse:
    repo = get_repo()
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    try:
        repo.reserve_daily_slot(day)
    except DailyCapReached as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    now = int(time.time())
    job = Job(
        job_id=uuid.uuid4().hex,
        topic=req.topic,
        quality=req.quality,
        status=JobStatus.PENDING,
        created_at=now,
        ttl=now + CONFIG.job_ttl_days * 86400,
    )
    repo.create(job)

    if CONFIG.state_machine_arn:
        _start_execution(job)
        return JSONResponse(
            status_code=202,
            content={"job_id": job.job_id, "status": job.status.value},
        )

    # Local / MVP synchronous path.
    run_pipeline(job.job_id, job.topic, job.quality)
    done = repo.get(job.job_id)
    return JSONResponse(status_code=200, content=done.model_dump(mode="json") if done else {})


@app.get("/jobs/{job_id}")
def status(job_id: str) -> dict:
    job = get_repo().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.model_dump(mode="json")


def _start_execution(job: Job) -> None:
    import json

    import boto3

    boto3.client("stepfunctions", region_name=CONFIG.region).start_execution(
        stateMachineArn=CONFIG.state_machine_arn,
        name=job.job_id,
        input=json.dumps(
            {"job_id": job.job_id, "topic": job.topic, "quality": job.quality, "tokens_used": 0}
        ),
    )
