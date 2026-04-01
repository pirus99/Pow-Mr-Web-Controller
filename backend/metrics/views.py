import logging
from typing import Any, Dict

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .fetcher import get_battery_metrics, get_solax_metrics
from .prometheus_parser import flatten_metrics

logger = logging.getLogger(__name__)


def _serialize_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """Convert cached metrics result to a JSON-serializable form."""
    out = {
        'last_scraped': result.get('last_scraped'),
        'error': result.get('error'),
        'metrics': {},
    }
    data = result.get('data')
    if data:
        # Return structured form: metric_name -> list of {labels, value}
        out['metrics'] = {
            name: samples
            for name, samples in data.items()
            if not name.startswith('python_gc') and not name.startswith('process_')
        }
    return out


class SolaxMetricsView(APIView):
    """GET /api/metrics/solax – live Solax inverter metrics."""

    def get(self, request):
        result = get_solax_metrics()
        return Response(_serialize_metrics(result))


class BatteryMetricsView(APIView):
    """GET /api/metrics/battery – live Battery (Daly BMS) metrics."""

    def get(self, request):
        result = get_battery_metrics()
        return Response(_serialize_metrics(result))


class PrometheusExportView(APIView):
    """
    GET /metrics – Prometheus-compatible exposition of all metrics
    (PowMr inverter + Solax + Battery).
    """

    def get(self, request):
        from inverter.modbus_client import read_inverter_status

        lines = []

        # ---- PowMr inverter metrics ----
        inv = read_inverter_status()
        if inv and inv.get('connected'):
            powmr_gauges = {
                'powmr_ac_voltage_volts': ('AC Voltage', inv.get('ac_voltage')),
                'powmr_ac_frequency_hertz': ('AC Frequency', inv.get('ac_frequency')),
                'powmr_pv_voltage_volts': ('PV Voltage', inv.get('pv_voltage')),
                'powmr_battery_voltage_volts': ('Battery Voltage', inv.get('battery_voltage')),
                'powmr_battery_soc_percent': ('Battery State of Charge', inv.get('battery_soc')),
                'powmr_battery_charge_current_amperes': ('Battery Charge Current', inv.get('battery_charge_current')),
                'powmr_battery_discharge_current_amperes': ('Battery Discharge Current', inv.get('battery_discharge_current')),
                'powmr_load_power_watts': ('Load Power', inv.get('load_power')),
                'powmr_load_percent': ('Load Percent', inv.get('load_percent')),
                'powmr_output_source_priority': ('Output Source Priority', inv.get('output_source_priority')),
                'powmr_charger_source_priority': ('Charger Source Priority', inv.get('charger_source_priority')),
                'powmr_temperature_celsius': ('Inverter Temperature', inv.get('temperature')),
            }
            for metric_name, (help_text, value) in powmr_gauges.items():
                if value is not None:
                    lines.append(f'# HELP {metric_name} {help_text}')
                    lines.append(f'# TYPE {metric_name} gauge')
                    lines.append(f'{metric_name} {value}')

        # ---- Solax metrics (pass-through) ----
        solax_result = get_solax_metrics()
        if solax_result.get('data'):
            for name, samples in solax_result['data'].items():
                if name.startswith('python_gc') or name.startswith('process_'):
                    continue
                lines.append(f'# HELP {name} (from Solax exporter)')
                lines.append(f'# TYPE {name} gauge')
                for sample in samples:
                    labels_str = ''
                    if sample['labels']:
                        lparts = ','.join(f'{k}="{v}"' for k, v in sample['labels'].items())
                        labels_str = '{' + lparts + '}'
                    lines.append(f'{name}{labels_str} {sample["value"]}')

        # ---- Battery metrics (pass-through) ----
        batt_result = get_battery_metrics()
        if batt_result.get('data'):
            for name, samples in batt_result['data'].items():
                if name.startswith('python_gc') or name.startswith('process_'):
                    continue
                lines.append(f'# HELP {name} (from Battery exporter)')
                lines.append(f'# TYPE {name} gauge')
                for sample in samples:
                    labels_str = ''
                    if sample['labels']:
                        lparts = ','.join(f'{k}="{v}"' for k, v in sample['labels'].items())
                        labels_str = '{' + lparts + '}'
                    lines.append(f'{name}{labels_str} {sample["value"]}')

        content = '\n'.join(lines) + '\n'
        return HttpResponse(content, content_type='text/plain; version=0.0.4; charset=utf-8')
