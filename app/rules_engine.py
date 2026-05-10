"""Shared data store, rule engine, and metric/action metadata."""

import json
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Metric catalogue (used in UI dropdowns) ───────────────────────────────────

AVAILABLE_METRICS = {
    "battery": {
        # key = suffix after "daly_bms_"
        "soc_percent":                    "Battery SOC (%)",
        "pack_voltage_volts":             "Pack Voltage (V)",
        "pack_current_amperes":           "Pack Current (A, + = charging)",
        "temperature_max_celsius":        "Max Temperature (°C)",
        "temperature_min_celsius":        "Min Temperature (°C)",
        "remaining_capacity_ampere_hours":"Remaining Capacity (Ah)",
        "cell_voltage_max_volts":         "Max Cell Voltage (V)",
        "cell_voltage_min_volts":         "Min Cell Voltage (V)",
        "cell_voltage_delta_volts":       "Cell Voltage Delta (V)",
        "charge_discharge_cycles_total":  "Charge/Discharge Cycles",
    },
    "solax": {
        # key = suffix after "solax_"  (label_filter inverter required)
        "grid_power_watts":               "Grid Power (W)",
        "pv1_power_watts":                "PV1 Power (W)",
        "pv2_power_watts":                "PV2 Power (W)",
        "feedin_power_watts":             "Feed-in Power (W, + = export)",
        "grid_voltage_volts":             "Grid Voltage (V)",
        "grid_current_amperes":           "Grid Current (A)",
        "inverter_temperature_celsius":   "Inverter Temperature (°C)",
        "daily_energy_kwh":               "Daily Energy (kWh)",
        "inverter_status":                "Inverter Status (2 = Normal)",
    },
    "powmr": {
        # key = field name in PowMr data dict
        "battery_soc":               "Battery SOC (%)",
        "battery_voltage":           "Battery Voltage (V)",
        "battery_charge_current":    "Battery Charge Current (A)",
        "battery_discharge_current": "Battery Discharge Current (A)",
        "load_power":                "Load Power (W)",
        "load_percent":              "Load Percent (%)",
        "ac_input_voltage":          "AC Input Voltage (V)",
        "pv_voltage":                "PV Voltage (V)",
        "output_source_priority":    "Output Source Priority (0/1/2)",
        "charger_source_priority":   "Charger Source Priority (0-3)",
    },
}

AVAILABLE_ACTIONS = [
    {
        "register": 5018,
        "name": "Output Source Priority",
        "type": "select",
        "options": [
            {"value": 0, "label": "USB (Utility→Solar→Battery)"},
            {"value": 1, "label": "SUB (Solar→Utility→Battery)"},
            {"value": 2, "label": "SBU (Solar→Battery→Utility)"},
        ],
    },
    {
        "register": 5017,
        "name": "Charger Source Priority",
        "type": "select",
        "options": [
            {"value": 0, "label": "Utility First"},
            {"value": 1, "label": "Solar First"},
            {"value": 2, "label": "Solar + Utility"},
            {"value": 3, "label": "Solar Only"},
        ],
    },
    {
        "register": 5024,
        "name": "Utility Charge Current (A)",
        "type": "select",
        "options": [
            {"value": 2,  "label": "2 A"},
            {"value": 10, "label": "10 A"},
            {"value": 20, "label": "20 A"},
            {"value": 30, "label": "30 A"},
            {"value": 40, "label": "40 A"},
            {"value": 50, "label": "50 A"},
            {"value": 60, "label": "60 A"},
        ],
    },
    {
        "register": 5022,
        "name": "Max Total Charge Current (A)",
        "type": "number",
        "min": 10,
        "max": 80,
    },
    {
        "register": 5002,
        "name": "Buzzer Alarm",
        "type": "select",
        "options": [{"value": 0, "label": "Off"}, {"value": 1, "label": "On"}],
    },
]


# ── Thread-safe data store ────────────────────────────────────────────────────


class DataStore:
    """Holds the latest polled data from all three sources."""

    def __init__(self):
        self._lock = threading.Lock()
        self._battery = {"metrics": {}, "data": {}, "error": None, "last_update": None}
        self._solax   = {"metrics": {}, "data": {}, "error": None, "last_update": None}
        self._powmr   = {"data": {},                "error": None, "last_update": None}

    # ── Writers (called from background scheduler) ────────────────────────────

    def update_battery(self, metrics, normalised, error):
        with self._lock:
            self._battery = {
                "metrics":     metrics,
                "data":        normalised,
                "error":       error,
                "last_update": _now(),
            }

    def update_solax(self, metrics, normalised, error):
        with self._lock:
            self._solax = {
                "metrics":     metrics,
                "data":        normalised,
                "error":       error,
                "last_update": _now(),
            }

    def update_powmr(self, data, error):
        with self._lock:
            self._powmr = {
                "data":        data or {},
                "error":       error,
                "last_update": _now(),
            }

    # ── Readers ───────────────────────────────────────────────────────────────

    def get_snapshot(self):
        """Return a deep-copy-safe snapshot of the current state."""
        with self._lock:
            return {
                "battery": dict(self._battery),
                "solax":   dict(self._solax),
                "powmr":   dict(self._powmr),
            }

    def get_metric_value(self, source, metric, label_filter=None):
        """Resolve a single metric value for rule evaluation."""
        with self._lock:
            if source == "battery":
                name = f"daly_bms_{metric}"
                return _lookup(self._battery["metrics"], name, label_filter)
            if source == "solax":
                name = f"solax_{metric}"
                return _lookup(self._solax["metrics"], name, label_filter)
            if source == "powmr":
                return self._powmr["data"].get(metric)
        return None

    def get_solax_inverters(self):
        """Return sorted list of known Solax inverter names."""
        with self._lock:
            return sorted(self._solax["data"].keys())


# ── Rule engine ───────────────────────────────────────────────────────────────


class RulesEngine:
    """Evaluates automation rules on configurable intervals."""

    OPERATORS = {
        "<":  lambda a, b: a < b,
        ">":  lambda a, b: a > b,
        "<=": lambda a, b: a <= b,
        ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    def __init__(self, data_store, powmr_client, db_module):
        self.store  = data_store
        self.powmr  = powmr_client
        self.db     = db_module
        self._sched = None
        self._cooldowns: "dict[int, datetime]" = {}
        self._lock  = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        from apscheduler.schedulers.background import BackgroundScheduler  # noqa: PLC0415

        self._sched = BackgroundScheduler(daemon=True)
        self._sched.start()
        for rule in self.db.get_rules():
            if rule["enabled"]:
                self._schedule(rule)
        logger.info("Rules engine started")

    def stop(self):
        if self._sched:
            self._sched.shutdown(wait=False)

    # ── Dynamic rule management (called from Flask routes) ────────────────────

    def on_rule_created(self, rule):
        if rule["enabled"]:
            self._schedule(rule)

    def on_rule_updated(self, rule):
        self._unschedule(rule["id"])
        if rule["enabled"]:
            self._schedule(rule)

    def on_rule_deleted(self, rule_id):
        self._unschedule(rule_id)
        with self._lock:
            self._cooldowns.pop(rule_id, None)

    # ── Scheduling helpers ────────────────────────────────────────────────────

    def _schedule(self, rule):
        self._sched.add_job(
            self._evaluate,
            "interval",
            seconds=rule["interval_seconds"],
            id=f"rule_{rule['id']}",
            args=[rule["id"]],
            replace_existing=True,
        )

    def _unschedule(self, rule_id):
        try:
            self._sched.remove_job(f"rule_{rule_id}")
        except Exception:
            pass

    # ── Evaluation ────────────────────────────────────────────────────────────

    def _evaluate(self, rule_id):
        rule = self.db.get_rule(rule_id)
        if not rule or not rule["enabled"]:
            return

        now = datetime.now(timezone.utc)

        # Cooldown check
        with self._lock:
            last = self._cooldowns.get(rule_id)
        if last and (now - last).total_seconds() < rule["cooldown_seconds"]:
            return

        try:
            conditions_met = all(
                self._check_condition(c) for c in rule["conditions"]
            )
        except Exception as exc:
            msg = f"Condition error: {exc}"
            logger.error("Rule %d – %s", rule_id, msg)
            self.db.add_rule_log(rule_id, False, msg)
            return

        if not conditions_met:
            self.db.add_rule_log(rule_id, False, "Conditions not met")
            return

        # Execute action
        action = rule["action"]
        ok, err = self.powmr.write_register(action["register"], action["value"])
        if ok:
            msg = (
                f"Set register {action['register']} = {action['value']} "
                f"({action.get('description', '')})"
            )
            logger.info("Rule '%s': %s", rule["name"], msg)
            with self._lock:
                self._cooldowns[rule_id] = now
            self.db.set_rule_last_triggered(rule_id, now.isoformat())
        else:
            msg = f"Write failed: {err}"
            logger.error("Rule '%s': %s", rule["name"], msg)
        self.db.add_rule_log(rule_id, ok, msg)

    def _check_condition(self, cond):
        value = self.store.get_metric_value(
            cond["source"], cond["metric"], cond.get("label_filter") or None
        )
        if value is None:
            raise ValueError(
                f"Metric {cond['source']}.{cond['metric']} is not available"
            )
        op = self.OPERATORS.get(cond["operator"])
        if op is None:
            raise ValueError(f"Unknown operator '{cond['operator']}'")
        return op(float(value), float(cond["value"]))


# ── Private utilities ─────────────────────────────────────────────────────────


def _now():
    return datetime.now(timezone.utc).isoformat()


def _lookup(metrics, name, label_filter):
    entries = metrics.get(name, [])
    if not entries:
        return None
    if not label_filter:
        return entries[0]["value"]
    for e in entries:
        if all(e["labels"].get(k) == v for k, v in label_filter.items()):
            return e["value"]
    return None
