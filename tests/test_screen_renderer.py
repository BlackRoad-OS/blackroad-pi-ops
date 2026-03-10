"""Tests for screen_renderer (no pygame or MQTT broker required)."""

from __future__ import annotations

import json
import queue
import time

import pytest

import screen_renderer as sr
from screen_renderer import DisplayMode, Message, ScreenRenderer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def renderer(monkeypatch):
    """Return a ScreenRenderer with pygame and MQTT stubbed out."""
    monkeypatch.setattr(sr, "PYGAME_AVAILABLE", False)
    monkeypatch.setattr(sr, "mqtt", None)
    return ScreenRenderer(width=640, height=480)


# ---------------------------------------------------------------------------
# Message dataclass
# ---------------------------------------------------------------------------


def test_message_defaults():
    msg = Message(text="hello")
    assert msg.text == "hello"
    assert msg.color == (255, 255, 255)
    assert msg.timestamp == 0.0
    assert msg.duration == 5.0


def test_message_custom_fields():
    msg = Message(text="hi", color=(0, 255, 0), timestamp=1.0, duration=10.0)
    assert msg.color == (0, 255, 0)
    assert msg.duration == 10.0


# ---------------------------------------------------------------------------
# DisplayMode enum
# ---------------------------------------------------------------------------


def test_display_mode_values():
    assert DisplayMode.HOLOGRAM.value == "hologram"
    assert DisplayMode.STATUS.value == "status"
    assert DisplayMode.SCROLL.value == "scroll"
    assert DisplayMode.DASHBOARD.value == "dashboard"


# ---------------------------------------------------------------------------
# ScreenRenderer initialisation
# ---------------------------------------------------------------------------


def test_renderer_defaults(renderer):
    assert renderer.width == 640
    assert renderer.height == 480
    assert renderer.mode == DisplayMode.HOLOGRAM
    assert renderer.screen is None
    assert renderer.mqtt_client is None


# ---------------------------------------------------------------------------
# _handle_message: system/hologram/text
# ---------------------------------------------------------------------------


def test_handle_hologram_text(renderer):
    renderer._handle_message("system/hologram/text", "Hello Pi")
    assert renderer.mode == DisplayMode.HOLOGRAM
    msg = renderer.messages.get_nowait()
    assert msg.text == "Hello Pi"
    assert msg.color == renderer.CYAN
    assert msg.duration == 5.0


# ---------------------------------------------------------------------------
# _handle_message: system/panel/status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,expected_color_attr",
    [
        ("ok", "GREEN"),
        ("success", "GREEN"),
        ("warning", "ORANGE"),
        ("error", "RED"),
        ("info", "BLUE"),
    ],
)
def test_handle_status_color_mapping(renderer, status, expected_color_attr):
    payload = json.dumps({"status": status, "message": "Test"})
    renderer._handle_message("system/panel/status", payload)
    assert renderer.mode == DisplayMode.STATUS
    msg = renderer.messages.get_nowait()
    assert msg.color == getattr(renderer, expected_color_attr)


def test_handle_status_default_color(renderer):
    """Unknown status should produce WHITE."""
    payload = json.dumps({"status": "unknown"})
    renderer._handle_message("system/panel/status", payload)
    msg = renderer.messages.get_nowait()
    assert msg.color == renderer.WHITE


def test_handle_status_text_from_payload(renderer):
    payload = json.dumps({"status": "ok", "message": "All systems go"})
    renderer._handle_message("system/panel/status", payload)
    msg = renderer.messages.get_nowait()
    assert msg.text == "All systems go"


def test_handle_status_text_falls_back_to_status(renderer):
    """When 'message' key is absent the status string is uppercased."""
    payload = json.dumps({"status": "warning"})
    renderer._handle_message("system/panel/status", payload)
    msg = renderer.messages.get_nowait()
    assert msg.text == "WARNING"


def test_handle_status_invalid_json_ignored(renderer):
    """Invalid JSON on the status topic should not enqueue anything."""
    renderer._handle_message("system/panel/status", "not-json")
    assert renderer.messages.empty()


def test_handle_status_duration(renderer):
    payload = json.dumps({"status": "ok", "message": "ok"})
    renderer._handle_message("system/panel/status", payload)
    msg = renderer.messages.get_nowait()
    assert msg.duration == 10.0


# ---------------------------------------------------------------------------
# _handle_message: agent/output
# ---------------------------------------------------------------------------


def test_handle_agent_output(renderer):
    renderer._handle_message("agent/output", "task done")
    assert renderer.mode == DisplayMode.SCROLL
    assert len(renderer.scroll_messages) == 1
    assert renderer.scroll_messages[0].text == "task done"
    assert renderer.scroll_messages[0].color == renderer.GREEN


def test_handle_agent_output_does_not_use_queue(renderer):
    """Agent output goes into scroll_messages, not the messages queue."""
    renderer._handle_message("agent/output", "line 1")
    assert renderer.messages.empty()


def test_handle_agent_output_scroll_limit(renderer):
    """scroll_messages should keep at most 10 entries."""
    for i in range(15):
        renderer._handle_message("agent/output", f"line {i}")
    assert len(renderer.scroll_messages) == 10
    # Oldest entries are dropped; most recent is last
    assert renderer.scroll_messages[-1].text == "line 14"


# ---------------------------------------------------------------------------
# _handle_message: screen/command
# ---------------------------------------------------------------------------


def test_handle_command_clear(renderer):
    renderer._handle_message("agent/output", "some text")
    renderer.current_message = Message(text="prev", timestamp=time.time(), duration=60.0)

    renderer._handle_message("screen/command", json.dumps({"command": "clear"}))

    assert renderer.scroll_messages == []
    assert renderer.current_message is None


def test_handle_command_mode_change(renderer):
    payload = json.dumps({"command": "mode", "mode": "dashboard"})
    renderer._handle_message("screen/command", payload)
    assert renderer.mode == DisplayMode.DASHBOARD


def test_handle_command_invalid_mode_ignored(renderer):
    payload = json.dumps({"command": "mode", "mode": "nonexistent"})
    renderer._handle_message("screen/command", payload)
    # Mode should remain at the default
    assert renderer.mode == DisplayMode.HOLOGRAM


def test_handle_command_invalid_json_ignored(renderer):
    renderer._handle_message("screen/command", "bad{json")
    assert renderer.mode == DisplayMode.HOLOGRAM


# ---------------------------------------------------------------------------
# render() without pygame
# ---------------------------------------------------------------------------


def test_render_without_pygame_prints_error(renderer, capsys):
    renderer.render()
    captured = capsys.readouterr()
    assert "pygame not available" in captured.out


# ---------------------------------------------------------------------------
# stop() without connections
# ---------------------------------------------------------------------------


def test_stop_sets_running_false(renderer):
    renderer.running = True
    renderer.stop()
    assert renderer.running is False
