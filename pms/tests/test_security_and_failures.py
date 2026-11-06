import json
import logging
import time

import pytest

from app.config import PLACEHOLDER_SECRET
from app.main import JsonFormatter
from tests.conftest import AUTH, SECRET

TOOL_PATHS = ["find-reservation", "check-availability", "request-late-checkout", "create-ticket"]
BODY = {"phone": "5550100001"}


def test_health_is_public(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "failure_mode": "none"}


@pytest.mark.parametrize("path", TOOL_PATHS)
def test_missing_secret_is_401(client, path):
    assert client.post(f"/tools/{path}", json={}).status_code == 401


@pytest.mark.parametrize("path", TOOL_PATHS)
def test_wrong_secret_is_401(client, path):
    res = client.post(f"/tools/{path}", json={}, headers={"X-Tool-Secret": "wrong"})
    assert res.status_code == 401


def test_error_mode_returns_503_immediately(make_client):
    client = make_client(failure_mode="error")
    start = time.perf_counter()
    res = client.post("/tools/find-reservation", json=BODY, headers=AUTH)
    assert res.status_code == 503
    assert time.perf_counter() - start < 0.5


def test_timeout_mode_waits_past_timeout_then_503(make_client):
    client = make_client(failure_mode="timeout", timeout_seconds=0.1)
    start = time.perf_counter()
    res = client.post("/tools/find-reservation", json=BODY, headers=AUTH)
    assert res.status_code == 503
    assert time.perf_counter() - start > 0.1


@pytest.mark.parametrize("mode", ["timeout", "error"])
def test_auth_is_checked_before_failure_simulation(make_client, mode):
    client = make_client(failure_mode=mode, timeout_seconds=0)
    assert client.post("/tools/find-reservation", json=BODY).status_code == 401


def test_health_stays_up_during_simulated_outage(make_client):
    res = make_client(failure_mode="error").get("/health")
    assert res.status_code == 200
    assert res.json()["failure_mode"] == "error"


def test_invalid_failure_mode_is_rejected(make_client):
    with pytest.raises(ValueError):
        make_client(failure_mode="flaky")


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))


def test_logs_are_structured_and_hide_phone_and_secret(client):
    handler = ListHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("pms")
    logger.addHandler(handler)
    try:
        client.post("/tools/find-reservation", json={"phone": "+52 55 5010 0001"}, headers=AUTH)
    finally:
        logger.removeHandler(handler)

    entries = [json.loads(line) for line in handler.lines]
    request_log = next(e for e in entries if e["msg"] == "request")
    assert request_log["endpoint"] == "/tools/find-reservation"
    assert request_log["status"] == 200
    assert isinstance(request_log["duration_ms"], float)
    everything = "\n".join(handler.lines)
    assert "5550100001" not in everything
    assert "***0001" in everything
    assert SECRET not in everything


def test_placeholder_secret_from_env_example_is_rejected(make_client):
    with pytest.raises(ValueError):
        make_client(tool_secret=PLACEHOLDER_SECRET)
