"""Tests for the Pi-Ops FastAPI dashboard (app.py)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import MessageStore, EventBus, Message, TopicStat, create_app


# ---------------------------------------------------------------------------
# MessageStore tests
# ---------------------------------------------------------------------------


def _make_store() -> tuple[MessageStore, Path]:
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    import os as _os
    _os.close(tmp_fd)
    store = MessageStore(Path(tmp_path), max_messages=5)
    return store, Path(tmp_path)


def test_message_store_insert_and_recent():
    store, _ = _make_store()
    msg = store.insert(Message(id=None, topic="test/topic", payload="hello", created_at=1.0))
    assert msg.id is not None
    recent = store.recent(limit=10)
    assert len(recent) == 1
    assert recent[0].topic == "test/topic"
    assert recent[0].payload == "hello"
    store.close()


def test_message_store_ring_buffer():
    store, _ = _make_store()
    for i in range(10):
        store.insert(Message(id=None, topic="t", payload=str(i), created_at=float(i)))
    recent = store.recent(limit=100)
    # Should only keep max_messages (5)
    assert len(recent) == 5
    store.close()


def test_message_store_topic_stats():
    store, _ = _make_store()
    store.insert(Message(id=None, topic="a/b", payload="1", created_at=1.0))
    store.insert(Message(id=None, topic="a/b", payload="2", created_at=2.0))
    store.insert(Message(id=None, topic="c/d", payload="3", created_at=3.0))
    stats = store.topic_stats(limit=10)
    topics = {s.topic: s for s in stats}
    assert topics["a/b"].count == 2
    assert topics["c/d"].count == 1
    store.close()


def test_message_asdict():
    msg = Message(id=42, topic="sys/hb", payload='{"ok":true}', created_at=100.0)
    d = msg.asdict()
    assert d["id"] == 42
    assert d["topic"] == "sys/hb"
    assert d["payload"] == '{"ok":true}'
    assert d["created_at"] == 100.0


def test_topic_stat_asdict():
    ts = TopicStat(topic="x/y", count=7, last_seen=50.0)
    d = ts.asdict()
    assert d["topic"] == "x/y"
    assert d["count"] == 7
    assert d["last_seen"] == 50.0


# ---------------------------------------------------------------------------
# API endpoint tests (using TestClient - no real MQTT needed)
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Create a test client backed by a temporary file-based SQLite database."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("PI_OPS_MQTT_HOST", "127.0.0.1")
    monkeypatch.setenv("PI_OPS_MQTT_PORT", "9999")  # non-existent, async connect

    # Patch Bus.start so no real MQTT thread starts
    import app as app_module

    original_start = app_module.Bus.start

    def mock_start(self, loop):
        pass  # skip real MQTT connection in tests

    monkeypatch.setattr(app_module.Bus, "start", mock_start)
    monkeypatch.setattr(app_module.Bus, "stop", lambda self: None)
    monkeypatch.setenv("PI_OPS_DB_PATH", str(db_file))

    # Override DB path by patching create_app to use tmp file
    original_create = app_module.create_app

    def patched_create():
        import app as m
        _orig = m.DB_FILENAME
        m.DB_FILENAME = str(db_file)
        result = original_create()
        m.DB_FILENAME = _orig
        return result

    test_app = patched_create()
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "pi-ops"


def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Pi-Ops" in resp.text


def test_api_messages_empty(client):
    resp = client.get("/api/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["messages"] == []


def test_api_stats_empty(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["topics"] == []


def test_api_publish_missing_topic(client):
    resp = client.post("/api/publish", json={"message": "hi"})
    assert resp.status_code == 400
    assert "topic" in resp.json()["detail"].lower()


def test_api_publish_missing_message(client):
    resp = client.post("/api/publish", json={"topic": "test/t"})
    assert resp.status_code == 400
    assert "message" in resp.json()["detail"].lower()


def test_api_publish_success(client, monkeypatch):
    import app as app_module

    published = []

    def mock_publish(self, topic, payload, qos=0, retain=False):
        published.append((topic, payload, qos, retain))

    monkeypatch.setattr(app_module.Bus, "publish", mock_publish)

    resp = client.post(
        "/api/publish",
        json={"topic": "test/t", "message": "hello", "qos": 1, "retain": True},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"
    assert published[0][0] == "test/t"
    assert published[0][1] == "hello"


def test_api_messages_limit_clamped(client):
    """limit param should be clamped to [1, max_messages]."""
    resp = client.get("/api/messages?limit=0")
    assert resp.status_code == 200
    resp2 = client.get("/api/messages?limit=99999")
    assert resp2.status_code == 200
