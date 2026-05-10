"""Lightweight Prometheus metrics re-export server on a configurable port.

Exposes:
  • daly_bms_* metrics (filtered from the BMS endpoint)
  • solax_*     metrics (filtered from the Solax endpoint)
  • powmr_*     metrics (generated from the DataStore)
"""

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

logger = logging.getLogger(__name__)

# Module-level references set by start()
_battery_url: str = ""
_solax_url: str = ""
_data_store = None
_fetch_timeout: int = 5


def start(port, battery_url, solax_url, data_store, fetch_timeout=5, host=""):
    global _battery_url, _solax_url, _data_store, _fetch_timeout
    _battery_url   = battery_url
    _solax_url     = solax_url
    _data_store    = data_store
    _fetch_timeout = fetch_timeout

    server = HTTPServer((host, port), _Handler)
    t = threading.Thread(target=server.serve_forever, name="metrics-server", daemon=True)
    t.start()
    logger.info("Prometheus metrics server started on port %d", port)
    return server


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        body = _build_metrics().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # suppress access logs
        pass


def _build_metrics():
    parts = []

    # ── BMS metrics ───────────────────────────────────────────────────────────
    parts.append(_fetch_filtered(_battery_url, "daly_bms_"))

    # ── Solax metrics ─────────────────────────────────────────────────────────
    parts.append(_fetch_filtered(_solax_url, "solax_"))

    # ── PowMr metrics ─────────────────────────────────────────────────────────
    if _data_store:
        snap = _data_store.get_snapshot()
        parts.append(_generate_powmr(snap["powmr"]["data"]))

    return "\n".join(p for p in parts if p)


def _fetch_filtered(url, prefix):
    """Fetch a Prometheus endpoint, return only lines for metrics matching prefix."""
    try:
        from prometheus_client.parser import text_string_to_metric_families  # noqa: PLC0415

        resp = requests.get(url, timeout=_fetch_timeout)
        resp.raise_for_status()
        lines = []
        for family in text_string_to_metric_families(resp.text):
            if not family.name.startswith(prefix):
                continue
            lines.append(f"# HELP {family.name} {family.documentation}")
            lines.append(f"# TYPE {family.name} {family.type}")
            for sample in family.samples:
                lbl = ",".join(f'{k}="{v}"' for k, v in sample.labels.items())
                name_part = f"{sample.name}{{{lbl}}}" if lbl else sample.name
                lines.append(f"{name_part} {sample.value}")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("metrics_server: failed to fetch %s – %s", url, exc)
        return ""


_POWMR_METRICS = [
    ("powmr_battery_voltage_volts",          "gauge", "Battery voltage (V)",                      "battery_voltage"),
    ("powmr_battery_soc_percent",            "gauge", "Battery state of charge (%)",               "battery_soc"),
    ("powmr_battery_charge_current_amperes", "gauge", "Battery charge current (A)",                "battery_charge_current"),
    ("powmr_battery_discharge_current_amp",  "gauge", "Battery discharge current (A)",             "battery_discharge_current"),
    ("powmr_ac_input_voltage_volts",         "gauge", "AC input voltage (V)",                      "ac_input_voltage"),
    ("powmr_ac_input_frequency_hertz",       "gauge", "AC input frequency (Hz)",                   "ac_input_frequency"),
    ("powmr_pv_voltage_volts",               "gauge", "PV input voltage (V)",                      "pv_voltage"),
    ("powmr_load_voltage_volts",             "gauge", "Load voltage (V)",                          "load_voltage"),
    ("powmr_load_power_watts",               "gauge", "Load power (W)",                            "load_power"),
    ("powmr_load_va",                        "gauge", "Load apparent power (VA)",                  "load_va"),
    ("powmr_load_percent",                   "gauge", "Load percentage (%)",                       "load_percent"),
    ("powmr_output_source_priority",         "gauge", "Output source priority (0=USB 1=SUB 2=SBU)","output_source_priority"),
    ("powmr_charger_source_priority",        "gauge", "Charger source priority",                   "charger_source_priority"),
    ("powmr_charger_status",                 "gauge", "Charger status (0=Off 1=Idle 2=Active)",    "charger_status"),
    ("powmr_temperature_celsius",            "gauge", "Inverter temperature (°C)",                 "temperature"),
    ("powmr_error_code",                     "gauge", "Error code (0 = no error)",                 "error_code"),
]

_POWMR_BOOL_METRICS = [
    ("powmr_on_battery",   "1 if running on battery",       "on_battery"),
    ("powmr_ac_active",    "1 if AC input is active",        "ac_active"),
    ("powmr_load_enabled", "1 if load output is enabled",    "load_enabled"),
]


def _generate_powmr(data):
    if not data:
        return ""

    lines = []
    for prom_name, prom_type, description, data_key in _POWMR_METRICS:
        value = data.get(data_key)
        if value is None:
            continue
        lines.append(f"# HELP {prom_name} {description}")
        lines.append(f"# TYPE {prom_name} {prom_type}")
        lines.append(f"{prom_name} {value}")

    for prom_name, description, data_key in _POWMR_BOOL_METRICS:
        value = data.get(data_key)
        if value is None:
            continue
        lines.append(f"# HELP {prom_name} {description}")
        lines.append(f"# TYPE {prom_name} gauge")
        lines.append(f"{prom_name} {int(value)}")

    return "\n".join(lines)
