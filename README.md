# PowMr Web Controller

A full-stack web application to **monitor and control a PowMr solar inverter** via RS232/RS485, while also aggregating metrics from **Solax inverters** and a **Daly BMS battery** system.

## Features

- **Real-time Dashboard** – view PowMr inverter status, Solax inverter metrics, and Daly BMS battery data in one place
- **Inverter Control** – set Output Source Priority, Charger Source Priority, Utility Charge Current, and all other PowMr Modbus registers via a web interface
- **Automation Rules Engine** – define rules like:
  - _"If solax_feedin_power_watts > 400 W for 60 s → switch PowMr to Utility First"_
  - _"If feedin_power_watts < 0 W for 120 s → switch back to SBU mode"_
- **Prometheus Metrics Export** – `/metrics` endpoint exports all metrics (PowMr + Solax + Battery) in Prometheus text format for Grafana/Alertmanager integration
- **Activity Log** – view when automation rules were triggered and what actions were taken

## Architecture

```
Angular Frontend (port 80) ──→ Django REST API (port 8000) ──→ PowMr Inverter (RS232)
                                        │
                                        ├──→ Solax Prometheus endpoint
                                        └──→ Daly BMS Prometheus endpoint
```

## Hardware Setup

The PowMr inverter uses an **RJ45 RS232 connector** on its left side:

| Pin | Color | Signal |
|-----|-------|--------|
| 8 | Brown | GND |
| 4 | Blue | +12V |
| 2 | Orange | RX (data to inverter) |
| 1 | White/Orange | TX (data from inverter) |

Connect via a USB-RS232 adapter to your host. Protocol: **2400 baud, 8N1, Modbus RTU, slave ID 5**.

## Quick Start (Docker Compose)

```bash
# 1. Clone the repository
git clone https://github.com/pirus99/Pow-Mr-Web-Controller.git
cd Pow-Mr-Web-Controller

# 2. Configure environment (edit docker-compose.yml)
#    - Set POWMR_PORT to your RS232/USB device (e.g. /dev/ttyUSB0)
#    - Set SOLAX_METRICS_URL and BATTERY_METRICS_URL
#    - Change DJANGO_SECRET_KEY

# 3. Start
docker compose up -d

# 4. Open http://localhost in your browser
```

## Development Setup

### Backend (Django DRF)

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
# API available at http://localhost:8000
```

### Frontend (Angular)

```bash
cd frontend
npm install
ng serve
# UI available at http://localhost:4200
```

## Configuration

### Environment Variables (Backend)

| Variable | Default | Description |
|----------|---------|-------------|
| `POWMR_PORT` | `/dev/ttyUSB0` | Serial port for PowMr inverter |
| `POWMR_BAUDRATE` | `2400` | Baud rate (PowMr uses 2400) |
| `POWMR_SLAVE_ID` | `5` | Modbus slave ID |
| `POWMR_TIMEOUT` | `3` | Serial timeout in seconds |
| `SOLAX_METRICS_URL` | `http://localhost:9090/metrics` | Solax Prometheus exporter URL |
| `BATTERY_METRICS_URL` | `http://localhost:9091/metrics` | Battery BMS Prometheus exporter URL |
| `DJANGO_SECRET_KEY` | _(insecure default)_ | Django secret key – **change in production** |
| `DJANGO_DEBUG` | `True` | Debug mode |

## API Reference

### Inverter

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/inverter/status/` | Live inverter readings |
| GET | `/api/inverter/options/` | Valid values for all controllable settings |
| POST | `/api/inverter/control/` | Write a register value |

**Write register example:**
```json
POST /api/inverter/control/
{"register": "output_source_priority", "value": 0}
```

**Register options:**
- `output_source_priority`: 0=Utility First, 1=Solar First, 2=SBU
- `charger_source_priority`: 0=Utility First, 1=Solar First, 2=Solar+Utility, 3=Only Solar
- `utility_charge_current`: one of `[2, 10, 20, 30, 40, 50, 60]` A

### Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/metrics/solax/` | Scraped Solax metrics (JSON) |
| GET | `/api/metrics/battery/` | Scraped Battery BMS metrics (JSON) |
| GET | `/metrics` | All metrics in Prometheus format |

### Automation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/automation/rules/` | List / create rules |
| GET/PUT/DELETE | `/api/automation/rules/<id>/` | Get / update / delete rule |
| POST | `/api/automation/rules/<id>/toggle/` | Enable/disable rule |
| GET | `/api/automation/logs/` | Activity log |

## Automation Rule Example

```json
{
  "name": "Grid when excess solar",
  "description": "Switch to grid when Solax is exporting > 400W",
  "enabled": true,
  "metric_source": "solax",
  "metric_name": "solax_feedin_power_watts",
  "metric_labels": {"inverter": "garage"},
  "operator": ">",
  "threshold": 400,
  "duration_seconds": 60,
  "action_register": "output_source_priority",
  "action_value": 0,
  "reset_register": "output_source_priority",
  "reset_value": 2,
  "reset_duration_seconds": 120
}
```

## PowMr Modbus Register Map

Based on [leodesigner/powmr_comm](https://github.com/leodesigner/powmr_comm):

### Read (status) registers (starting at 4501)
| Register | Description |
|----------|-------------|
| 4502 | AC Voltage |
| 4503 | AC Frequency |
| 4504 | PV Voltage |
| 4506 | Battery Voltage |
| 4507 | Battery SoC (%) |
| 4508 | Battery Charge Current |
| 4509 | Battery Discharge Current |
| 4512 | Load Power (W) |
| 4536 | Charger Source Priority |
| 4537 | Output Source Priority |

### Write (control) registers
| Register | Name | Values |
|----------|------|--------|
| 5017 | Charger Source Priority | 0–3 |
| 5018 | Output Source Priority | 0–2 |
| 5024 | Utility Charge Current | 2,10,20,30,40,50,60 A |
| 5022 | Max Total Charge Current | 10–80 A |
| 5002 | Buzzer Alarm | 0–1 |

Full register map: [odya/esphome-powmr-hybrid-inverter](https://github.com/odya/esphome-powmr-hybrid-inverter/blob/main/docs/registers-map.md)

## License

MIT
