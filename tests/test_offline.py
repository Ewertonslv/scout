"""Offline mode: the pipeline must run end-to-end with no AWS and no real LLM.

This is the path the local ``demo.py`` and CI smoke both exercise, so it needs to
produce a coherent, cited, topic-threaded brief on its own.
"""
import time
from dataclasses import replace

import pytest

from core import deps
from core.config import CONFIG
from core.models import Job, JobStatus
from core.offline import InMemoryJobRepository, OfflineBedrockClient
from core.pipeline import run_pipeline
from core.repo import DailyCapReached


@pytest.fixture
def offline_wired():
    deps.set_client(OfflineBedrockClient())
    deps.set_repo(InMemoryJobRepository())
    yield deps.get_repo()
    deps._client = None
    deps._repo = None


def test_offline_pipeline_produces_topic_brief(offline_wired):
    repo = offline_wired
    now = int(time.time())
    topic = "serverless vs containers"
    repo.create(Job(job_id="off1", topic=topic, created_at=now, ttl=now + 3600))

    state = run_pipeline("off1", topic)

    assert state["status"] == JobStatus.DONE.value
    md = state["brief"]["markdown"]
    assert "serverless vs containers" in md          # topic threaded planner -> synthesizer
    assert state["brief"]["citations"]               # at least one [n] source extracted
    assert state["tokens_used"] > 0                  # budget was charged

    persisted = repo.get("off1")
    assert persisted is not None and persisted.status == JobStatus.DONE


def test_offline_repo_enforces_daily_cap():
    repo = InMemoryJobRepository()
    for _ in range(3):
        repo.reserve_daily_slot("2026-07-15", limit=3)
    with pytest.raises(DailyCapReached):
        repo.reserve_daily_slot("2026-07-15", limit=3)


def test_deps_select_offline_impls(monkeypatch):
    monkeypatch.setattr(deps, "CONFIG", replace(CONFIG, offline=True))
    monkeypatch.setattr(deps, "_client", None)
    monkeypatch.setattr(deps, "_repo", None)

    assert isinstance(deps.get_client(), OfflineBedrockClient)
    assert isinstance(deps.get_repo(), InMemoryJobRepository)

    deps._client = None
    deps._repo = None
