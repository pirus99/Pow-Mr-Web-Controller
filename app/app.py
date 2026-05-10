"""PowMr Web Controller – main Flask application."""

import json
import logging
import os
import signal
import sys
from typing import Optional

from flask import Flask, jsonify, render_template, request

from database import (
    add_rule_log,
    create_rule,
    delete_rule,
    get_rule,
    get_rule_logs,
    get_rules,
    init_db,
    set_rule_last_triggered,
    update_rule,
)
from fetcher import fetch_battery_metrics, fetch_solax_metrics, normalise_battery, normalise_solax
from powmr import PowMrClient, WRITABLE_REGISTERS
from rules_engine import AVAILABLE_ACTIONS, AVAILABLE_METRICS, DataStore, RulesEngine
import metrics_server as metrics_srv

# ── Configuration ─────────────────────────────────────────────────────────────

from dotenv import load_dotenv

load_dotenv()

SERIAL_PORT   = os.getenv("SERIAL_PORT",   "/dev/ttyUSB1")
SERIAL_BAUD   = int(os.getenv("SERIAL_BAUD", "2400"))
BATTERY_URL   = os.getenv("BATTERY_URL",   "http://localhost:8000/metrics")
SOLAX_URL     = os.getenv("SOLAX_URL",     "http://localhost:9000/metrics")
WEB_HOST      = os.getenv("WEB_HOST",      "0.0.0.0")
WEB_PORT      = int(os.getenv("WEB_PORT",  "5000"))
METRICS_PORT  = int(os.getenv("METRICS_PORT", "8002"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))
FETCH_TIMEOUT = int(os.getenv("FETCH_TIMEOUT", "5"))
SECRET_KEY    = os.getenv("SECRET_KEY",    "change-me-please")

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ── Globals (initialised in start_services) ───────────────────────────────────

_data_store: Optional[DataStore] = None
_powmr_client: Optional[PowMrClient] = None
_rules_engine: Optional[RulesEngine] = None
_poll_scheduler = None


# ── Service initialisation ────────────────────────────────────────────────────


def _poll_all():
    """Fetch fresh data from all sources and update the DataStore."""
    bms_raw, bms_err = fetch_battery_metrics(BATTERY_URL, timeout=FETCH_TIMEOUT)
    bms_norm = normalise_battery(bms_raw) if bms_raw else {}
    _data_store.update_battery(bms_raw, bms_norm, bms_err)

    sol_raw, sol_err = fetch_solax_metrics(SOLAX_URL, timeout=FETCH_TIMEOUT)
    sol_norm = normalise_solax(sol_raw) if sol_raw else {}
    _data_store.update_solax(sol_raw, sol_norm, sol_err)

    pmr_data, pmr_err = _powmr_client.read_data()
    _data_store.update_powmr(pmr_data, pmr_err)


def start_services():
    global _data_store, _powmr_client, _rules_engine, _poll_scheduler

    init_db()

    _data_store   = DataStore()
    _powmr_client = PowMrClient(SERIAL_PORT, SERIAL_BAUD)

    # Initial data poll (non-blocking on failure)
    try:
        _poll_all()
    except Exception as exc:
        logger.warning("Initial poll failed: %s", exc)

    # Background data poller
    from apscheduler.schedulers.background import BackgroundScheduler  # noqa: PLC0415

    _poll_scheduler = BackgroundScheduler(daemon=True)
    _poll_scheduler.add_job(_poll_all, "interval", seconds=POLL_INTERVAL, id="poll_all")
    _poll_scheduler.start()

    # Rules engine
    import database as db_module  # noqa: PLC0415

    _rules_engine = RulesEngine(_data_store, _powmr_client, db_module)
    _rules_engine.start()

    # Prometheus re-export server
    metrics_srv.start(
        METRICS_PORT, BATTERY_URL, SOLAX_URL, _data_store, FETCH_TIMEOUT,
        host=os.getenv("METRICS_HOST", "0.0.0.0"),
    )

    logger.info(
        "PowMr Web Controller started – web: %s:%d  metrics: :%d  poll: %ds",
        WEB_HOST, WEB_PORT, METRICS_PORT, POLL_INTERVAL,
    )


# ── HTML pages ────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/rules")
def rules_page():
    return render_template("rules.html")


# ── API – live data ───────────────────────────────────────────────────────────


@app.route("/api/data")
def api_data():
    snap = _data_store.get_snapshot()
    return jsonify(
        {
            "battery": {
                "connected":   snap["battery"]["error"] is None,
                "error":       snap["battery"]["error"],
                "last_update": snap["battery"]["last_update"],
                **snap["battery"]["data"],
            },
            "solax": {
                "connected":   snap["solax"]["error"] is None,
                "error":       snap["solax"]["error"],
                "last_update": snap["solax"]["last_update"],
                "inverters":   snap["solax"]["data"],
            },
            "powmr": {
                "connected":   snap["powmr"]["error"] is None,
                "error":       snap["powmr"]["error"],
                "last_update": snap["powmr"]["last_update"],
                **snap["powmr"]["data"],
            },
        }
    )


@app.route("/api/metadata")
def api_metadata():
    return jsonify(
        {
            "available_metrics":  AVAILABLE_METRICS,
            "available_actions":  AVAILABLE_ACTIONS,
            "writable_registers": WRITABLE_REGISTERS,
            "solax_inverters":    _data_store.get_solax_inverters(),
        }
    )


# ── API – PowMr control ───────────────────────────────────────────────────────


@app.route("/api/powmr/control", methods=["POST"])
def api_powmr_control():
    body = request.get_json(force=True) or {}
    register = body.get("register")
    value    = body.get("value")

    if register is None or value is None:
        return jsonify({"error": "register and value are required"}), 400

    ok, err = _powmr_client.write_register(int(register), int(value))

    # Refresh PowMr data immediately so dashboard shows the new value
    if ok:
        try:
            data, e2 = _powmr_client.read_data()
            _data_store.update_powmr(data, e2)
        except Exception:
            pass

    if ok:
        return jsonify({"success": True})
    logger.error("PowMr control write failed: %s", err)
    return jsonify({"error": "Failed to apply setting – check server logs."}), 500


# ── API – Rules ───────────────────────────────────────────────────────────────


@app.route("/api/rules", methods=["GET"])
def api_list_rules():
    return jsonify(get_rules())


@app.route("/api/rules", methods=["POST"])
def api_create_rule():
    body = request.get_json(force=True) or {}
    try:
        rule_id = create_rule(
            name             = str(body["name"]),
            enabled          = bool(body.get("enabled", True)),
            interval_seconds = int(body.get("interval_seconds", 60)),
            cooldown_seconds = int(body.get("cooldown_seconds", 300)),
            conditions       = body["conditions"],
            action           = body["action"],
        )
    except KeyError as exc:
        return jsonify({"error": f"Missing required field: {exc}"}), 400
    except ValueError:
        return jsonify({"error": "Invalid field value"}), 400

    rule = get_rule(rule_id)
    _rules_engine.on_rule_created(rule)
    return jsonify(rule), 201


@app.route("/api/rules/<int:rule_id>", methods=["GET"])
def api_get_rule(rule_id):
    rule = get_rule(rule_id)
    if rule is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(rule)


@app.route("/api/rules/<int:rule_id>", methods=["PUT"])
def api_update_rule(rule_id):
    if get_rule(rule_id) is None:
        return jsonify({"error": "not found"}), 404

    body = request.get_json(force=True) or {}
    allowed = {"name", "enabled", "interval_seconds", "cooldown_seconds", "conditions", "action"}
    kwargs = {k: v for k, v in body.items() if k in allowed}
    update_rule(rule_id, **kwargs)

    rule = get_rule(rule_id)
    _rules_engine.on_rule_updated(rule)
    return jsonify(rule)


@app.route("/api/rules/<int:rule_id>", methods=["DELETE"])
def api_delete_rule(rule_id):
    if get_rule(rule_id) is None:
        return jsonify({"error": "not found"}), 404
    _rules_engine.on_rule_deleted(rule_id)
    delete_rule(rule_id)
    return "", 204


@app.route("/api/rules/<int:rule_id>/toggle", methods=["POST"])
def api_toggle_rule(rule_id):
    rule = get_rule(rule_id)
    if rule is None:
        return jsonify({"error": "not found"}), 404
    update_rule(rule_id, enabled=not rule["enabled"])
    rule = get_rule(rule_id)
    _rules_engine.on_rule_updated(rule)
    return jsonify(rule)


@app.route("/api/rules/<int:rule_id>/logs", methods=["GET"])
def api_rule_logs(rule_id):
    if get_rule(rule_id) is None:
        return jsonify({"error": "not found"}), 404
    limit = min(int(request.args.get("limit", 50)), 100)
    return jsonify(get_rule_logs(rule_id, limit=limit))


# ── Entry point ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    start_services()

    def _shutdown(sig, frame):
        logger.info("Shutting down…")
        if _poll_scheduler:
            _poll_scheduler.shutdown(wait=False)
        if _rules_engine:
            _rules_engine.stop()
        if _powmr_client:
            _powmr_client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)

    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, threaded=True, use_reloader=False)
