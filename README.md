# PowMr Web Controller

A lightweight Python/Flask web application that monitors and controls a **PowMr hybrid inverter** (POW-HVM3.2H-24V and similar) via RS485/RS232 Modbus, alongside a **Daly BMS** and **Solax solar inverters** exposed via Prometheus endpoints.

---

## Features

| Feature | Details |
|---|---|
| **Live dashboard** | BMS SOC, pack voltage/current, cell voltages, Solax grid/PV power, PowMr load/AC/PV |
| **Inverter controls** | Change output priority, charger priority, charge currents, voltages directly from the UI |
| **Automation rules** | Define IF-THEN rules (e.g. SOC < 20 % → USB mode) with per-rule evaluation intervals and cooldowns |
| **Prometheus export** | Re-exports `daly_bms_*`, `solax_*` and `powmr_*` metrics on port 8002 for Grafana |
| **systemd service** | Runs as a proper system daemon |

---

## Hardware / topology

```
Raspberry Pi  ←→  USB–RS485 adapter  ←→  RS485–RS232 adapter  ←→  PowMr RJ45
```

- Modbus RTU, 2400 baud, 8N1, slave ID 5
- Default serial port: `/dev/ttyUSB1`

---

## Quick start

```bash
# 1. Clone / copy to target directory
sudo mkdir -p /opt/powmr-controller
sudo cp -r app /opt/powmr-controller/

# 2. Create virtual environment and install dependencies
python3 -m venv /opt/powmr-controller/venv
/opt/powmr-controller/venv/bin/pip install -r /opt/powmr-controller/app/requirements.txt

# 3. Create .env from template
cp /opt/powmr-controller/app/.env.example /opt/powmr-controller/app/.env
# Edit .env to match your setup

# 4. Install systemd service
sudo cp powmr-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now powmr-controller

# 5. Check status
sudo systemctl status powmr-controller
sudo journalctl -u powmr-controller -f
```

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `SERIAL_PORT` | `/dev/ttyUSB1` | Serial device for PowMr |
| `SERIAL_BAUD` | `2400` | Baud rate |
| `BATTERY_URL` | `http://localhost:8000/metrics` | Daly BMS Prometheus endpoint |
| `SOLAX_URL` | `http://localhost:9000/metrics` | Solax Prometheus endpoint |
| `WEB_HOST` | `0.0.0.0` | Web interface bind address |
| `WEB_PORT` | `5000` | Web interface port |
| `METRICS_PORT` | `8002` | Prometheus re-export port |
| `POLL_INTERVAL` | `15` | Data poll interval (seconds) |
| `FETCH_TIMEOUT` | `5` | HTTP fetch timeout (seconds) |

---

## Automation rules

Rules are created via the **Automation Rules** page in the web UI.

**Example – Low SOC → USB mode**
- Condition: `Battery BMS → soc_percent < 20`
- Action: Output Source Priority = USB (Utility→Solar→Battery)
- Interval: 60 s, Cooldown: 300 s

**Example – High SOC + grid export → SBU mode**
- Condition 1: `Battery BMS → soc_percent > 80`
- Condition 2: `Solax (garage) → feedin_power_watts > -100`
- Action: Output Source Priority = SBU (Solar→Battery→Utility)
- Interval: 60 s, Cooldown: 300 s

---

## Prometheus / Grafana

Metrics are available at `http://<pi-ip>:8002/metrics` and include:

- All `daly_bms_*` metrics from the BMS exporter
- All `solax_*` metrics from the Solax exporter
- `powmr_battery_voltage_volts`, `powmr_battery_soc_percent`, `powmr_load_power_watts`, … (full list in `metrics_server.py`)

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/data` | Current live data (JSON) |
| GET | `/api/metadata` | Available metrics, actions, registers |
| POST | `/api/powmr/control` | Write a PowMr register `{register, value}` |
| GET | `/api/rules` | List rules |
| POST | `/api/rules` | Create rule |
| PUT | `/api/rules/<id>` | Update rule |
| DELETE | `/api/rules/<id>` | Delete rule |
| POST | `/api/rules/<id>/toggle` | Enable / disable rule |
| GET | `/api/rules/<id>/logs` | Rule execution log |
