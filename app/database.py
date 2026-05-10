"""SQLite persistence layer for automation rules and execution logs."""

import sqlite3
import json
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "powmr.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rules (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    NOT NULL,
                enabled          INTEGER NOT NULL DEFAULT 1,
                interval_seconds INTEGER NOT NULL DEFAULT 60,
                cooldown_seconds INTEGER NOT NULL DEFAULT 300,
                conditions       TEXT    NOT NULL,
                action           TEXT    NOT NULL,
                last_triggered   TEXT,
                created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rule_logs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id   INTEGER NOT NULL,
                timestamp TEXT    NOT NULL,
                triggered INTEGER NOT NULL,
                message   TEXT,
                FOREIGN KEY (rule_id) REFERENCES rules(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


# ── Rules CRUD ────────────────────────────────────────────────────────────────

def get_rules():
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM rules ORDER BY id").fetchall()
    return [_parse_rule(dict(r)) for r in rows]


def get_rule(rule_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
    return _parse_rule(dict(row)) if row else None


def create_rule(name, enabled, interval_seconds, cooldown_seconds, conditions, action):
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO rules (name, enabled, interval_seconds, cooldown_seconds, conditions, action)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                int(bool(enabled)),
                int(interval_seconds),
                int(cooldown_seconds),
                json.dumps(conditions),
                json.dumps(action),
            ),
        )
        conn.commit()
        return cur.lastrowid


def update_rule(rule_id, **kwargs):
    # Each entry maps the caller's key to the exact SQL fragment (no user input
    # ever reaches the query string itself — only bound parameters).
    _FIELD_SQL = {
        "name":             "name = ?",
        "enabled":          "enabled = ?",
        "interval_seconds": "interval_seconds = ?",
        "cooldown_seconds": "cooldown_seconds = ?",
        "conditions":       "conditions = ?",
        "action":           "action = ?",
    }
    sets, values = [], []
    for k, v in kwargs.items():
        sql_fragment = _FIELD_SQL.get(k)
        if sql_fragment is None:
            continue
        sets.append(sql_fragment)
        if k in ("conditions", "action") and not isinstance(v, str):
            v = json.dumps(v)
        elif k == "enabled":
            v = int(bool(v))
        values.append(v)
    if not sets:
        return
    values.append(rule_id)
    # `sets` contains only hardcoded strings from _FIELD_SQL; no injection risk.
    sql = "UPDATE rules SET " + ", ".join(sets) + " WHERE id = ?"
    with _connect() as conn:
        conn.execute(sql, values)
        conn.commit()


def delete_rule(rule_id):
    with _connect() as conn:
        conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        conn.commit()


def set_rule_last_triggered(rule_id, timestamp):
    with _connect() as conn:
        conn.execute("UPDATE rules SET last_triggered = ? WHERE id = ?", (timestamp, rule_id))
        conn.commit()


# ── Rule logs ─────────────────────────────────────────────────────────────────

def add_rule_log(rule_id, triggered, message):
    ts = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO rule_logs (rule_id, timestamp, triggered, message) VALUES (?, ?, ?, ?)",
            (rule_id, ts, int(bool(triggered)), message),
        )
        # Keep only the last 100 log entries per rule
        conn.execute(
            """
            DELETE FROM rule_logs
            WHERE rule_id = ? AND id NOT IN (
                SELECT id FROM rule_logs WHERE rule_id = ? ORDER BY id DESC LIMIT 100
            )
            """,
            (rule_id, rule_id),
        )
        conn.commit()


def get_rule_logs(rule_id, limit=50):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM rule_logs WHERE rule_id = ? ORDER BY id DESC LIMIT ?",
            (rule_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_rule(rule):
    rule["conditions"] = json.loads(rule["conditions"])
    rule["action"] = json.loads(rule["action"])
    rule["enabled"] = bool(rule["enabled"])
    return rule
