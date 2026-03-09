"""Tests for led_bridge (using MOCK backend, no hardware required)."""

from __future__ import annotations

import time
import pytest

from led_bridge import (
    LEDBackend,
    LEDController,
    LEDState,
    PulsePattern,
    RainbowPattern,
    FlashPattern,
    StatusPattern,
    LEDBridge,
)


@pytest.fixture()
def controller():
    return LEDController(num_pixels=8, backend=LEDBackend.MOCK)


def test_led_controller_defaults(controller):
    assert controller.num_pixels == 8
    assert controller.backend == LEDBackend.MOCK
    assert len(controller.pixels) == 8


def test_set_pixel(controller):
    controller.set_pixel(0, 255, 0, 0)
    assert controller.pixels[0].r == 255
    assert controller.pixels[0].g == 0
    assert controller.pixels[0].b == 0


def test_set_pixel_out_of_range(controller):
    # Should not raise; simply ignore
    controller.set_pixel(99, 255, 0, 0)


def test_set_all(controller):
    controller.set_all(0, 255, 0)
    for px in controller.pixels:
        assert px.g == 255


def test_clear(controller):
    controller.set_all(200, 200, 200)
    controller.clear()
    for px in controller.pixels:
        assert px.r == 0
        assert px.g == 0
        assert px.b == 0


def test_show_mock(controller, capsys):
    controller.set_pixel(0, 255, 0, 0)
    controller.show()
    captured = capsys.readouterr()
    assert "🔴" in captured.out


def test_pulse_pattern(controller):
    pattern = PulsePattern(controller, (0, 255, 0), duration=0.1)
    done = False
    for _ in range(10):
        done = pattern.update()
        time.sleep(0.02)
        if done:
            break
    assert done is True


def test_rainbow_pattern(controller):
    pattern = RainbowPattern(controller, duration=0.1)
    done = False
    for _ in range(10):
        done = pattern.update()
        time.sleep(0.02)
        if done:
            break
    assert done is True


def test_flash_pattern(controller):
    pattern = FlashPattern(controller, (255, 0, 0), flashes=1)
    done = False
    for _ in range(20):
        done = pattern.update()
        time.sleep(0.02)
        if done:
            break
    assert done is True


def test_status_pattern(controller):
    pattern = StatusPattern(controller, (0, 0, 255), duration=0.1)
    done = False
    for _ in range(10):
        done = pattern.update()
        time.sleep(0.02)
        if done:
            break
    assert done is True


@pytest.fixture()
def bridge(controller, monkeypatch):
    """LEDBridge fixture with MOCK LED backend and no real MQTT client."""
    import unittest.mock as mock

    monkeypatch.setattr("led_bridge.mqtt", mock.MagicMock())
    b = LEDBridge(num_pixels=8)
    b.controller = controller
    return b


def test_led_bridge_handle_heartbeat(bridge):
    bridge._handle_message("system/heartbeat/agent1", "ping")
    assert not bridge.pattern_queue.empty()


def test_led_bridge_handle_hologram(bridge):
    bridge._handle_message("system/hologram/text", "Hello Pi")
    assert not bridge.pattern_queue.empty()


def test_led_bridge_handle_status(bridge):
    import json

    payload = json.dumps({"status": "ok"})
    bridge._handle_message("system/panel/status", payload)
    assert not bridge.pattern_queue.empty()


def test_led_bridge_handle_agent_output(bridge):
    bridge._handle_message("agent/output", "task done")
    assert not bridge.pattern_queue.empty()


def test_led_bridge_handle_custom_pattern(bridge):
    import json

    payload = json.dumps({"type": "rainbow", "duration": 1.0})
    bridge._handle_message("lights/pattern", payload)
    assert not bridge.pattern_queue.empty()
