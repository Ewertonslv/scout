import time

from core.models import Job, JobStatus
from core.pipeline import run_pipeline


def test_run_pipeline_produces_done_brief(wired):
    repo = wired
    now = int(time.time())
    repo.create(Job(job_id="job1", topic="quantum computing", created_at=now, ttl=now + 3600))

    state = run_pipeline("job1", "quantum computing")

    # End state carries the brief...
    assert state["status"] == JobStatus.DONE.value
    assert "Brief" in state["brief"]["markdown"]
    assert state["brief"]["citations"][0]["marker"] == "[1]"

    # ...and it was persisted.
    job = repo.get("job1")
    assert job.status == JobStatus.DONE
    assert job.brief is not None
    assert job.tokens_used > 0


def test_pipeline_fans_out_per_subtask(wired, fake_client):
    repo = wired
    now = int(time.time())
    repo.create(Job(job_id="job2", topic="t", created_at=now, ttl=now + 3600))
    run_pipeline("job2", "t")
    # planner(1) + 2 workers + critic(1) + synthesizer(1) = 5 model calls
    assert fake_client.calls == 5
