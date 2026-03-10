# BlackRoad Pi Ops

**Edge device management for Raspberry Pi and Jetson - LED control, screen rendering, and hardware interfaces.**

```bash
pip install blackroad-pi-ops
```

## What is this?

Pi Ops provides the edge computing layer for BlackRoad's agent infrastructure.
All three services communicate through an MQTT broker — publish a message on the
right topic and the LED strip lights up, the screen updates, and the dashboard
logs it instantly.

| Component | Description |
|-----------|-------------|
| **app.py** | FastAPI MQTT monitoring dashboard — REST API + live SSE stream |
| **led_bridge.py** | MQTT-to-LED translator — converts messages into WS281x animations |
| **screen_renderer.py** | MQTT-driven pygame display renderer — 4 visual modes |
| **pi_agent/** | Remote task executor — receives shell/Python tasks via WebSocket |

## Quick Start

### On Raspberry Pi

```bash
# Install with Pi-specific dependencies
pip install blackroad-pi-ops[rpi]

# Run the MQTT dashboard (requires an MQTT broker on localhost:1883)
pi-ops

# Or as a systemd service
sudo cp pi-ops.service /etc/systemd/system/
sudo systemctl enable pi-ops
sudo systemctl start pi-ops
```

### LED Bridge

The LED bridge subscribes to MQTT topics and drives a connected WS281x LED strip.

```bash
# Run against a local MQTT broker
led-bridge --mqtt-broker localhost --pixels 60

# Smoke-test all patterns without a broker
led-bridge --test
```

**MQTT topics consumed by led-bridge:**

| Topic | Effect |
|-------|--------|
| `system/heartbeat/#` | Green pulse |
| `system/hologram/text` | Rainbow scroll |
| `system/panel/status` | Status color (`{"status": "ok|warning|error"}`) |
| `agent/output` | Blue flash |
| `lights/pattern` | Custom JSON pattern (`{"type": "rainbow", "duration": 2.0}`) |

### Screen Renderer

The screen renderer subscribes to MQTT topics and renders them on a pygame display.

```bash
# Run against a local MQTT broker
python screen_renderer.py --mqtt-broker localhost --width 800 --height 480

# Smoke-test without a broker
python screen_renderer.py --test
```

**MQTT topics consumed by screen-renderer:**

| Topic | Display mode |
|-------|--------------|
| `system/hologram/text` | Hologram — pulsing cyan text with scanline effect |
| `system/panel/status` | Status — color-coded bar (`{"status": "ok", "message": "…"}`) |
| `agent/output` | Scroll — appends to a rolling list (last 10 kept) |
| `screen/command` | Control — `{"command": "clear"}` or `{"command": "mode", "mode": "dashboard"}` |

## Dashboard API Endpoints

`pi-ops` starts a FastAPI server (default port 8000).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/` | GET | Embedded HTML dashboard with live updates |
| `/api/messages` | GET | Recent MQTT messages (`?limit=100`) |
| `/api/stats` | GET | Per-topic message counts and last-seen times |
| `/api/publish` | POST | Publish an MQTT message (`{"topic": "…", "payload": "…"}`) |
| `/events` | GET | Server-Sent Events stream for real-time message push |

## Hardware Support

### Raspberry Pi
- Pi 4, Pi 3, Pi Zero 2 W
- WS281x LED strips (via GPIO18)
- SPI displays (ILI9341, ST7789, etc.)
- I2C OLED displays

### Jetson
- Jetson Nano, Xavier NX
- PWM LED control
- HDMI/DisplayPort output

## Wiring

### LED Strip (WS281x)
```
Pi GPIO18 (Pin 12) --> LED DIN
Pi 5V (Pin 2)      --> LED VCC
Pi GND (Pin 6)     --> LED GND
```

### SPI Display
```
Pi GPIO10 (MOSI)   --> Display SDA
Pi GPIO11 (SCLK)   --> Display SCL
Pi GPIO8 (CE0)     --> Display CS
Pi GPIO25          --> Display DC
Pi GPIO24          --> Display RST
```

## Configuration

Environment variables (see `.env.example`):

```bash
# MQTT broker
MQTT_BROKER=localhost
MQTT_PORT=1883

# LED settings
LED_COUNT=60
LED_PIN=18
LED_BRIGHTNESS=128

# Pi-Ops server
PI_OPS_PORT=8000
```

## Systemd Service

The included `pi-ops.service` file:

```ini
[Unit]
Description=BlackRoad Pi Ops
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/blackroad-pi-ops
ExecStart=/usr/local/bin/pi-ops
Restart=always

[Install]
WantedBy=multi-user.target
```

## License

MIT - See [LICENSE](LICENSE) for details.

---

Built by [BlackRoad OS](https://blackroad.io)

---

## 📜 License & Copyright

**Copyright © 2026 BlackRoad OS, Inc. All Rights Reserved.**

**CEO:** Alexa Amundson

**PROPRIETARY AND CONFIDENTIAL**

This software is the proprietary property of BlackRoad OS, Inc. and is **NOT for commercial resale**.

### ⚠️ Usage Restrictions:
- ✅ **Permitted:** Testing, evaluation, and educational purposes
- ❌ **Prohibited:** Commercial use, resale, or redistribution without written permission

### 🏢 Enterprise Scale:
Designed to support:
- 30,000 AI Agents
- 30,000 Human Employees
- One Operator: Alexa Amundson (CEO)

### 📧 Contact:
For commercial licensing inquiries:
- **Email:** blackroad.systems@gmail.com
- **Organization:** BlackRoad OS, Inc.

See [LICENSE](LICENSE) for complete terms.
