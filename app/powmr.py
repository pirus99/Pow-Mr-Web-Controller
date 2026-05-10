"""PowMr inverter Modbus RTU client.

Communication: RS232 Modbus at 2400 baud, slave ID 5.
Hardware chain: Raspberry Pi → USB-RS485 → RS485-RS232 → PowMr RJ45.

Register reference:
  https://github.com/leodesigner/powmr_comm
  https://github.com/odya/esphome-powmr-hybrid-inverter/blob/main/docs/registers-map.md
"""

import logging
import threading

logger = logging.getLogger(__name__)

SLAVE_ID = 5
BASE_REG_1 = 4501   # read 45 registers  → 4501–4545
COUNT_1 = 45
BASE_REG_2 = 4546   # read 16 registers  → 4546–4561
COUNT_2 = 16

OUTPUT_SOURCE_PRIORITY = {
    0: "USB (Utility→Solar→Battery)",
    1: "SUB (Solar→Utility→Battery)",
    2: "SBU (Solar→Battery→Utility)",
}
CHARGER_SOURCE_PRIORITY = {
    0: "Utility First",
    1: "Solar First",
    2: "Solar + Utility",
    3: "Solar Only",
}
CHARGER_STATUS = {0: "Off", 1: "Idle", 2: "Active"}

# Writable register metadata (used in dashboard controls and rules)
WRITABLE_REGISTERS = [
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
        "register": 5025,
        "name": "Back-to-Utility Voltage (V)",
        "type": "number",
        "min": 20.0,
        "max": 30.0,
        "step": 0.5,
        "scale": 10,   # value sent = display × scale
    },
    {
        "register": 5026,
        "name": "Back-to-Battery Voltage (V)",
        "type": "number",
        "min": 20.0,
        "max": 30.0,
        "step": 0.5,
        "scale": 10,
    },
    {
        "register": 5027,
        "name": "Bulk Charge Voltage (V)",
        "type": "number",
        "min": 24.0,
        "max": 32.0,
        "step": 0.1,
        "scale": 10,
    },
    {
        "register": 5028,
        "name": "Float Charge Voltage (V)",
        "type": "number",
        "min": 24.0,
        "max": 32.0,
        "step": 0.1,
        "scale": 10,
    },
    {
        "register": 5029,
        "name": "Low DC Cut-off Voltage (V)",
        "type": "number",
        "min": 20.0,
        "max": 26.0,
        "step": 0.1,
        "scale": 10,
    },
    {
        "register": 5002,
        "name": "Buzzer Alarm",
        "type": "select",
        "options": [{"value": 0, "label": "Off"}, {"value": 1, "label": "On"}],
    },
    {
        "register": 5007,
        "name": "Beep on Primary Source Fail",
        "type": "select",
        "options": [{"value": 0, "label": "Off"}, {"value": 1, "label": "On"}],
    },
    {
        "register": 5009,
        "name": "Overload Bypass",
        "type": "select",
        "options": [{"value": 0, "label": "Disabled"}, {"value": 1, "label": "Enabled"}],
    },
    {
        "register": 5005,
        "name": "Auto Restart on Overload",
        "type": "select",
        "options": [{"value": 0, "label": "Off"}, {"value": 1, "label": "On"}],
    },
    {
        "register": 5006,
        "name": "Auto Restart on Over-temperature",
        "type": "select",
        "options": [{"value": 0, "label": "Off"}, {"value": 1, "label": "On"}],
    },
]


class PowMrClient:
    """Thread-safe Modbus RTU client for the PowMr inverter."""

    def __init__(self, port, baudrate=2400):
        self._port = port
        self._baudrate = baudrate
        self._lock = threading.Lock()
        self._client = None
        self._connected = False
        self._init_client()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _init_client(self):
        try:
            from pymodbus.client import ModbusSerialClient  # noqa: PLC0415

            self._client = ModbusSerialClient(
                port=self._port,
                baudrate=self._baudrate,
                parity="N",
                stopbits=1,
                bytesize=8,
                timeout=3,
            )
        except Exception as exc:
            logger.error("Failed to initialise Modbus client: %s", exc)
            self._client = None

    def connect(self):
        if self._client is None:
            return False
        try:
            self._connected = self._client.connect()
            return self._connected
        except Exception as exc:
            logger.error("PowMr connect error: %s", exc)
            self._connected = False
            return False

    def disconnect(self):
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._connected = False

    # ── Public API ────────────────────────────────────────────────────────────

    def read_data(self):
        """Read all monitoring registers. Returns (data_dict | None, error | None)."""
        with self._lock:
            try:
                self._ensure_connected()
                r1 = self._read_holding(BASE_REG_1, COUNT_1)
                r2 = self._read_holding(BASE_REG_2, COUNT_2)
                return self._decode(r1, r2), None
            except Exception as exc:
                logger.error("PowMr read_data error: %s", exc)
                self._connected = False
                return None, str(exc)

    def write_register(self, address, value):
        """Write a single holding register. Returns (ok: bool, error | None)."""
        with self._lock:
            try:
                self._ensure_connected()
                result = self._client.write_register(
                    address=address, value=int(value) & 0xFFFF, slave=SLAVE_ID
                )
                if hasattr(result, "isError") and result.isError():
                    return False, str(result)
                return True, None
            except Exception as exc:
                logger.error("PowMr write_register(%d, %s) error: %s", address, value, exc)
                self._connected = False
                return False, str(exc)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ensure_connected(self):
        if not self._connected:
            if not self.connect():
                raise ConnectionError(f"Cannot connect to PowMr on {self._port}")

    def _read_holding(self, address, count):
        result = self._client.read_holding_registers(
            address=address, count=count, slave=SLAVE_ID
        )
        if hasattr(result, "isError") and result.isError():
            raise IOError(f"Modbus error reading {count} regs @ {address}: {result}")
        # The PowMr inverter transmits each 16-bit register in little-endian byte
        # order (low byte first), which is non-standard for Modbus RTU.  pymodbus
        # expects big-endian (high byte first), so every raw value has its two bytes
        # swapped.  Correct by swapping them back before returning.
        return [((v & 0xFF) << 8) | ((v >> 8) & 0xFF) for v in result.registers]

    @staticmethod
    def _decode(r1, r2):
        """Decode raw register arrays into a clean dictionary."""

        def flag(reg, bit):
            return bool(reg & bit)

        settings_flags = r1[34]   # reg 4535
        status_flags   = r2[7]    # reg 4553

        # Temperature at reg 4557 (index 11 of r2): stored directly in °C.
        raw_temp = r2[11] if len(r2) > 11 else 0
        temperature = raw_temp if raw_temp > 0 else None

        data = {
            # ── Measurements ────────────────────────────────────────────────
            "ac_input_voltage":          r1[1]  / 10.0,   # 4502
            "ac_input_frequency":        r1[2]  / 10.0,   # 4503
            "pv_voltage":                r1[3]  / 10.0,   # 4504
            "battery_voltage":           r1[5]  / 10.0,   # 4506
            "battery_soc":               r1[6],            # 4507
            "battery_charge_current":    r1[7]  / 10.0,   # 4508
            "battery_discharge_current": r1[8]  / 10.0,   # 4509
            "load_voltage":              r1[9]  / 10.0,   # 4510
            "load_frequency":            r1[10] / 10.0,   # 4511
            "load_power":                r1[11],           # 4512
            "load_va":                   r1[12],           # 4513
            "load_percent":              r1[13],           # 4514
            "error_code":                r1[29],           # 4530
            # ── Settings (readable) ─────────────────────────────────────────
            "charger_source_priority":   r1[35],           # 4536
            "output_source_priority":    r1[36],           # 4537
            "ac_input_voltage_range":    r1[37],           # 4538
            "target_output_frequency":   r1[39],           # 4540
            "max_total_charge_current":  r1[40],           # 4541
            "target_output_voltage":     r1[41],           # 4542
            "max_utility_charge_current":r1[42],           # 4543
            "back_to_utility_voltage":   r1[43] / 10.0,   # 4544
            "back_to_battery_voltage":   r1[44] / 10.0,   # 4545
            "bulk_charge_voltage":       r2[0]  / 10.0,   # 4546
            "float_charge_voltage":      r2[1]  / 10.0,   # 4547
            "low_cutoff_voltage":        r2[2]  / 10.0,   # 4548
            # ── Status flags ─────────────────────────────────────────────────
            "on_battery":   flag(status_flags, 0x100),
            "ac_active":    flag(status_flags, 0x200),
            "load_enabled": flag(status_flags, 0x4000),
            "charger_status": r2[9] if len(r2) > 9 else 0,  # 4555
            "temperature":  temperature,
            # ── Settings flags ───────────────────────────────────────────────
            "alarm_enabled":          flag(settings_flags, 0x100),
            "backlight_enabled":      flag(settings_flags, 0x400),
            "restart_on_overload":    flag(settings_flags, 0x800),
            "restart_on_overheat":    flag(settings_flags, 0x1000),
            "beep_on_primary_fail":   flag(settings_flags, 0x2000),
            "return_to_default_screen": flag(settings_flags, 0x4000),
            "overload_bypass":        flag(settings_flags, 0x8000),
            "battery_equalization":   flag(settings_flags, 0x2),
            "record_fault_code":      flag(settings_flags, 0x1),
        }

        # Human-readable labels
        data["output_source_priority_label"] = OUTPUT_SOURCE_PRIORITY.get(
            data["output_source_priority"], "Unknown"
        )
        data["charger_source_priority_label"] = CHARGER_SOURCE_PRIORITY.get(
            data["charger_source_priority"], "Unknown"
        )
        data["charger_status_label"] = CHARGER_STATUS.get(data["charger_status"], "Unknown")

        return data
