"""Fetch and normalise Prometheus metrics from the BMS and Solax endpoints."""

import logging

import requests

logger = logging.getLogger(__name__)

SOLAX_STATUS_LABELS = {
    -1: "Offline",
    0: "Waiting",
    1: "Checking",
    2: "Normal",
    3: "Fault",
    4: "Permanent Fault",
}


# ── Low-level fetch ───────────────────────────────────────────────────────────


def fetch_prometheus_metrics(url, prefix_filter=None, timeout=5):
    """Fetch a Prometheus /metrics endpoint and return a parsed dict.

    Returns:
        (metrics: dict, error: str | None)
        metrics = { metric_name: [ {labels: {}, value: float}, … ] }
    """
    try:
        from prometheus_client.parser import text_string_to_metric_families  # noqa: PLC0415

        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()

        result = {}
        for family in text_string_to_metric_families(resp.text):
            if prefix_filter and not any(family.name.startswith(p) for p in prefix_filter):
                continue
            for sample in family.samples:
                result.setdefault(sample.name, []).append(
                    {"labels": dict(sample.labels), "value": sample.value}
                )
        return result, None
    except Exception as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return {}, str(exc)


def fetch_raw_text(url, prefix, timeout=5):
    """Fetch a Prometheus endpoint and return only lines for *prefix* metrics.

    Used by the metrics re-export server on port 8002.
    """
    try:
        from prometheus_client.parser import text_string_to_metric_families  # noqa: PLC0415

        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()

        lines = []
        for family in text_string_to_metric_families(resp.text):
            if not family.name.startswith(prefix):
                continue
            lines.append(f"# HELP {family.name} {family.documentation}")
            lines.append(f"# TYPE {family.name} {family.type}")
            for sample in family.samples:
                lbl = ",".join(f'{k}="{v}"' for k, v in sample.labels.items())
                metric_str = f"{sample.name}{{{lbl}}}" if lbl else sample.name
                lines.append(f"{metric_str} {sample.value}")
        return "\n".join(lines) + "\n" if lines else ""
    except Exception as exc:
        logger.error("Failed to fetch raw text from %s: %s", url, exc)
        return ""


# ── Source-specific wrappers ──────────────────────────────────────────────────


def fetch_battery_metrics(url, timeout=5):
    return fetch_prometheus_metrics(url, prefix_filter=["daly_bms_"], timeout=timeout)


def fetch_solax_metrics(url, timeout=5):
    return fetch_prometheus_metrics(url, prefix_filter=["solax_"], timeout=timeout)


# ── Normalisation helpers ─────────────────────────────────────────────────────


def _scalar(metrics, name, labels=None):
    entries = metrics.get(name, [])
    if not entries:
        return None
    if not labels:
        return entries[0]["value"]
    for e in entries:
        if all(e["labels"].get(k) == v for k, v in labels.items()):
            return e["value"]
    return None


def normalise_battery(metrics):
    """Return a frontend-friendly dict from raw Daly BMS metrics."""
    g = lambda name: _scalar(metrics, name)  # noqa: E731

    cell_entries = sorted(
        metrics.get("daly_bms_cell_voltage_volts", []),
        key=lambda x: int(x["labels"].get("cell", 0)),
    )
    cells = [e["value"] for e in cell_entries]

    temp_entries = sorted(
        metrics.get("daly_bms_temperature_celsius", []),
        key=lambda x: int(x["labels"].get("sensor", 0)),
    )
    temps = [e["value"] for e in temp_entries]

    return {
        "soc":                   g("daly_bms_soc_percent"),
        "pack_voltage":          g("daly_bms_pack_voltage_volts"),
        "pack_current":          g("daly_bms_pack_current_amperes"),
        "temperature_max":       g("daly_bms_temperature_max_celsius"),
        "temperature_min":       g("daly_bms_temperature_min_celsius"),
        "remaining_capacity":    g("daly_bms_remaining_capacity_ampere_hours"),
        "cell_voltage_max":      g("daly_bms_cell_voltage_max_volts"),
        "cell_voltage_min":      g("daly_bms_cell_voltage_min_volts"),
        "cell_voltage_delta":    g("daly_bms_cell_voltage_delta_volts"),
        "cell_voltage_max_cell": g("daly_bms_cell_voltage_max_cell_number"),
        "cell_voltage_min_cell": g("daly_bms_cell_voltage_min_cell_number"),
        "charge_mos":            g("daly_bms_charge_mos_active") == 1.0,
        "discharge_mos":         g("daly_bms_discharge_mos_active") == 1.0,
        "cycle_count":           g("daly_bms_charge_discharge_cycles_total"),
        "cell_count":            g("daly_bms_cell_count"),
        "charger_connected":     g("daly_bms_charger_connected") == 1.0,
        "load_connected":        g("daly_bms_load_connected") == 1.0,
        "bms_up":                g("daly_bms_up") == 1.0,
        "cells":                 cells,
        "temperatures":          temps,
    }


def normalise_solax(metrics):
    """Return a dict of inverter → data from raw Solax metrics."""
    inverters = set()
    for entries in metrics.values():
        for e in entries:
            if "inverter" in e["labels"]:
                inverters.add(e["labels"]["inverter"])

    def gv(name, inv):
        return _scalar(metrics, name, {"inverter": inv})

    result = {}
    for inv in sorted(inverters):
        status_raw = gv("solax_inverter_status", inv)
        status_int = int(status_raw) if status_raw is not None else None
        result[inv] = {
            "grid_voltage":       gv("solax_grid_voltage_volts", inv),
            "grid_current":       gv("solax_grid_current_amperes", inv),
            "grid_power":         gv("solax_grid_power_watts", inv),
            "grid_frequency":     gv("solax_grid_frequency_hertz", inv),
            "pv1_voltage":        gv("solax_pv1_voltage_volts", inv),
            "pv2_voltage":        gv("solax_pv2_voltage_volts", inv),
            "pv1_current":        gv("solax_pv1_current_amperes", inv),
            "pv2_current":        gv("solax_pv2_current_amperes", inv),
            "pv1_power":          gv("solax_pv1_power_watts", inv),
            "pv2_power":          gv("solax_pv2_power_watts", inv),
            "feedin_power":       gv("solax_feedin_power_watts", inv),
            "total_energy":       gv("solax_total_energy_kwh", inv),
            "daily_energy":       gv("solax_daily_energy_kwh", inv),
            "total_feed_energy":  gv("solax_total_feed_energy_kwh", inv),
            "total_import_energy":gv("solax_total_import_energy_kwh", inv),
            "status":             status_int,
            "status_label":       SOLAX_STATUS_LABELS.get(status_int, "Unknown"),
            "temperature":        gv("solax_inverter_temperature_celsius", inv),
        }
    return result
