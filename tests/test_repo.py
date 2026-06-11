import time

import pytest

from core.models import Job, JobStatus
from core.repo import DailyCapReached


def _job(job_id="abc") -> Job:
    now = int(time.time())
    return Job(job_id=job_id, topic="t", created_at=now, ttl=now + 3600)


def test_create_and_get_roundtrip(repo):
    repo.create(_job())
    got = repo.get("abc")
    assert got is not None
    assert got.topic == "t"
    assert got.status == JobStatus.PENDING


def test_get_missing_returns_none(repo):
    assert repo.get("nope") is None


def test_update_status(repo):
    repo.create(_job())
    repo.update_status("abc", JobStatus.DONE)
    assert repo.get("abc").status == JobStatus.DONE


def test_daily_cap_enforced(repo):
    for _ in range(3):
        repo.reserve_daily_slot("2026-06-11", limit=3)
    with pytest.raises(DailyCapReached):
        repo.reserve_daily_slot("2026-06-11", limit=3)
