from fastapi.testclient import TestClient

from api.app import app


def test_healthz(wired):
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}


def test_submit_sync_returns_brief(wired):
    client = TestClient(app)
    resp = client.post("/jobs", json={"topic": "serverless architecture"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "DONE"
    assert "markdown" in body["brief"]


def test_status_roundtrip(wired):
    client = TestClient(app)
    job_id = client.post("/jobs", json={"topic": "edge computing"}).json()["job_id"]
    got = client.get(f"/jobs/{job_id}")
    assert got.status_code == 200
    assert got.json()["status"] == "DONE"


def test_status_404(wired):
    client = TestClient(app)
    assert client.get("/jobs/missing").status_code == 404


def test_daily_cap_returns_429(wired, monkeypatch):
    from core.repo import DailyCapReached

    def capped(day, limit=None):
        raise DailyCapReached("daily cap reached")

    monkeypatch.setattr(wired, "reserve_daily_slot", capped)
    client = TestClient(app)
    assert client.post("/jobs", json={"topic": "some topic"}).status_code == 429
