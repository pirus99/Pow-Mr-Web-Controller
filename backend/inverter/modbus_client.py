"""
PowMr Inverter Modbus/RS232 communication client.

Protocol: Modbus RTU over RS232 at 2400 baud, 8N1, slave ID 5.
Based on https://github.com/leodesigner/powmr_comm
"""

import logging
import threading
from typing import Optional, Dict, Any

from django.conf import settings

logger = logging.getLogger(__name__)

# Addresses for reading inverter status
STATUS_START_ADDR = 4501   # 45 registers
STATUS_COUNT = 45

SETTINGS_START_ADDR = 4546  # 16 registers
SETTINGS_COUNT = 16

# Charger source priority values (register 5017 / read: 4536)
CHARGER_SOURCE_PRIORITY = {
    0: 'Utility First',
    1: 'Solar First',
    2: 'Solar + Utility',
    3: 'Only Solar',
}

# Output source priority values (register 5018 / read: 4537)
OUTPUT_SOURCE_PRIORITY = {
    0: 'Utility First (USB)',
    1: 'Solar First (SUB)',
    2: 'SBU Priority',
}

# Allowed utility charge current values (register 5024)
UTILITY_CHARGE_CURRENT_VALUES = [2, 10, 20, 30, 40, 50, 60]

# Write-register addresses
WRITE_REGISTERS = {
    'buzzer_alarm': 5002,
    'backlight': 5004,
    'auto_restart_overload': 5005,
    'auto_restart_overheat': 5006,
    'beep_on_primary_fail': 5007,
    'auto_return_screen': 5008,
    'overload_bypass': 5009,
    'record_fault_code': 5010,
    'charger_source_priority': 5017,
    'output_source_priority': 5018,
    'ac_input_voltage_range': 5019,
    'battery_type': 5020,
    'output_frequency': 5021,
    'max_total_charge_current': 5022,
    'output_voltage': 5023,
    'utility_charge_current': 5024,
    'comeback_utility_voltage': 5025,
    'comeback_battery_voltage': 5026,
    'bulk_charging_voltage': 5027,
    'floating_charging_voltage': 5028,
    'low_dc_cutoff_voltage': 5029,
    'battery_equalization_voltage': 5030,
    'battery_equalized_time': 5031,
    'battery_equalized_timeout': 5032,
    'equalization_interval': 5033,
}

_client_lock = threading.Lock()
_modbus_client = None


def _is_client_connected(client: Any) -> bool:
    """
    Best-effort connectivity check compatible with multiple pymodbus versions.
    """
    if client is None:
        return False
    for attr_name in ('connected', 'is_socket_open'):
        try:
            # getattr is inside try because a property getter may raise
            attr = getattr(client, attr_name, None)
            if callable(attr):
                return bool(attr())
            if attr is not None:
                return bool(attr)
        except Exception:
            continue
    try:
        transport = getattr(client, 'transport', None)
        if transport is not None:
            is_open = getattr(transport, 'is_open', None)
            if isinstance(is_open, bool):
                return is_open
    except Exception:
        pass
    return False


def _reset_client_locked() -> None:
    """Close and clear cached client. Caller must hold _client_lock."""
    global _modbus_client
    if _modbus_client is not None:
        try:
            _modbus_client.close()
        except Exception:
            pass
    _modbus_client = None


def _reset_client() -> None:
    with _client_lock:
        _reset_client_locked()


def _build_client():
    try:
        try:
            from pymodbus import FramerType
            framer = FramerType.RTU
        except ImportError:
            # pymodbus < 3.6 uses a plain string for the framer
            framer = 'rtu'
        from pymodbus.client import ModbusSerialClient
        client = ModbusSerialClient(
            port=settings.POWMR_PORT,
            framer=framer,
            baudrate=settings.POWMR_BAUDRATE,
            bytesize=settings.POWMR_BYTESIZE,
            parity=settings.POWMR_PARITY,
            stopbits=settings.POWMR_STOPBITS,
            timeout=settings.POWMR_TIMEOUT,
        )
        if not client.connect():
            logger.error(
                "Could not connect to inverter serial port %s (baud=%s parity=%s stopbits=%s)",
                settings.POWMR_PORT,
                settings.POWMR_BAUDRATE,
                settings.POWMR_PARITY,
                settings.POWMR_STOPBITS,
            )
            return None
        return client
    except Exception as exc:
        logger.error("Could not connect to inverter on %s: %s", settings.POWMR_PORT, exc)
        return None


def _get_client():
    """Return a connected Modbus RTU client, creating one if needed."""
    global _modbus_client
    with _client_lock:
        if _is_client_connected(_modbus_client):
            return _modbus_client
        _reset_client_locked()
        _modbus_client = _build_client()
        return _modbus_client


def _parse_status_registers(regs: list) -> Dict[str, Any]:
    """
    Parse 45 status registers starting at address 4501.
    Index 0 = register 4501.
    """
    def _r(offset: int) -> int:
        try:
            return regs[offset]
        except IndexError:
            return 0

    flags_4516 = _r(15)   # reg 4516 (offset 15)
    flags_4535 = _r(34)   # reg 4535 (offset 34)
    flags_4553 = _r(52 - 4501)  # Beyond range, but 4535 is offset 34

    return {
        # Basic measurements
        'ac_voltage': _r(1) / 10.0,           # 4502
        'ac_frequency': _r(2) / 100.0,        # 4503
        'pv_voltage': _r(3) / 10.0,           # 4504
        'charging': bool(_r(4)),               # 4505
        'battery_voltage': _r(5) / 10.0,      # 4506
        'battery_soc': _r(6),                  # 4507 (%)
        'battery_charge_current': _r(7) / 10.0,    # 4508
        'battery_discharge_current': _r(8) / 10.0, # 4509
        'load_voltage': _r(9) / 10.0,         # 4510
        'load_frequency': _r(10) / 100.0,     # 4511
        'load_power': _r(11),                  # 4512 (W)
        'load_va': _r(12),                     # 4513
        'load_percent': _r(13),                # 4514 (%)
        # Binary flags (4516)
        'overload': bool(flags_4516 & 0x100),
        # Settings (read)
        'charger_source_priority': _r(35),     # 4536
        'output_source_priority': _r(36),      # 4537
        'ac_input_voltage_range': _r(37),      # 4538
        'target_output_frequency': _r(39),     # 4540
        'max_total_charge_current': _r(40),    # 4541
        'target_output_voltage': _r(41),       # 4542
        'max_utility_charge_current': _r(42),  # 4543
        'back_to_utility_voltage': _r(43),     # 4544
        'back_to_battery_voltage': _r(44),     # 4545
        # Human-readable labels
        'charger_source_priority_label': CHARGER_SOURCE_PRIORITY.get(_r(35), 'Unknown'),
        'output_source_priority_label': OUTPUT_SOURCE_PRIORITY.get(_r(36), 'Unknown'),
    }


def _parse_settings_registers(regs: list) -> Dict[str, Any]:
    """
    Parse 16 settings registers starting at address 4546.
    Index 0 = register 4546.
    """
    def _r(offset: int) -> int:
        try:
            return regs[offset]
        except IndexError:
            return 0

    flags_4553 = _r(7)  # reg 4553
    flags_4554 = _r(8)  # reg 4554

    return {
        'bulk_charging_voltage': _r(0) / 10.0,     # 4546
        'floating_charging_voltage': _r(1) / 10.0, # 4547
        'low_cutoff_voltage': _r(2) / 10.0,        # 4548
        'battery_eq_voltage': _r(3) / 10.0,        # 4549
        'battery_eq_time': _r(4),                   # 4550 (min)
        'battery_eq_timeout': _r(5),                # 4551 (min)
        'equalization_interval': _r(6),             # 4552 (day)
        # Status flags from 4553
        'on_battery': bool(flags_4553 & 0x100),
        'ac_active': bool(flags_4553 & 0x200),
        'load_off': bool(flags_4553 & 0x1000),
        'load_enabled': bool(flags_4553 & 0x4000),
        # Charger status 4555
        'charger_status': _r(9),                    # 4555
        'charger_status_label': ['Off', 'Idle', 'Active'][_r(9)] if _r(9) < 3 else 'Unknown',
        'temperature': _r(11),                      # 4557
    }


def read_inverter_status() -> Optional[Dict[str, Any]]:
    """
    Read and parse all inverter status and settings registers.
    Returns a dict of all values, or None on failure.
    """
    try:
        client = _get_client()
    except Exception as exc:
        logger.error("Error obtaining inverter client: %s", exc)
        _reset_client()
        return None

    if client is None:
        return None

    try:
        with _client_lock:
            # Read 45 status registers from 4501
            resp1 = client.read_holding_registers(
                address=STATUS_START_ADDR,
                count=STATUS_COUNT,
                slave=settings.POWMR_SLAVE_ID,
            )
            # Read 16 settings registers from 4546
            resp2 = client.read_holding_registers(
                address=SETTINGS_START_ADDR,
                count=SETTINGS_COUNT,
                slave=settings.POWMR_SLAVE_ID,
            )

        if resp1.isError() or resp2.isError():
            logger.warning("Modbus read error: %s / %s", resp1, resp2)
            _reset_client()
            return None

        status = _parse_status_registers(resp1.registers)
        settings_data = _parse_settings_registers(resp2.registers)
        status.update(settings_data)
        status['connected'] = True
        return status

    except Exception as exc:
        logger.error("Error reading inverter status: %s", exc)
        _reset_client()
        return None


def write_register(register_name: str, value: int) -> bool:
    """
    Write a single value to a named control register.
    Returns True on success.
    """
    address = WRITE_REGISTERS.get(register_name)
    if address is None:
        logger.error("Unknown register name: %s", register_name)
        return False

    try:
        client = _get_client()
    except Exception as exc:
        logger.error("Error obtaining inverter client: %s", exc)
        _reset_client()
        return False

    if client is None:
        return False

    try:
        with _client_lock:
            resp = client.write_register(
                address=address,
                value=value,
                slave=settings.POWMR_SLAVE_ID,
            )
        if resp.isError():
            logger.warning("Modbus write error for %s=%d: %s", register_name, value, resp)
            _reset_client()
            return False
        logger.info("Written %s=%d to register %d", register_name, value, address)
        return True
    except Exception as exc:
        logger.error("Error writing register %s: %s", register_name, exc)
        _reset_client()
        return False
