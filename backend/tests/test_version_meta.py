"""Which release is running: GET /v1/meta/version, public like /health."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_the_running_release_is_reported_without_signing_in(monkeypatch):
    monkeypatch.setenv("ARGUS_VERSION", "1.35.1")
    monkeypatch.setenv("ARGUS_COMMIT", "7df43fb")
    monkeypatch.setenv("ARGUS_BUILT_AT", "2026-10-05T19:00:00Z")
    got = client.get("/v1/meta/version")
    assert got.status_code == 200
    assert got.json() == {"version": "1.35.1", "commit": "7df43fb", "built_at": "2026-10-05T19:00:00Z",
                          "api_version": "1"}


def test_a_build_without_a_version_says_dev(monkeypatch):
    for k in ("ARGUS_VERSION", "ARGUS_COMMIT", "ARGUS_BUILT_AT"):
        monkeypatch.delenv(k, raising=False)
    assert client.get("/v1/meta/version").json()["version"] == "dev"
