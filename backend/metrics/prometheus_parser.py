"""
Parse Prometheus text exposition format.
Returns a dict: metric_name -> list of {labels: dict, value: float}
"""
import re
from typing import Dict, List, Any

SAMPLE_RE = re.compile(
    r'^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|NaN|[+-]Inf)\s*(?P<timestamp>\d+)?$'
)
LABEL_RE = re.compile(r'(\w+)="([^"]*)"')


def parse_prometheus_text(text: str) -> Dict[str, List[Dict[str, Any]]]:
    """Parse Prometheus text format into a dict of metric name -> list of samples."""
    result: Dict[str, List[Dict[str, Any]]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = SAMPLE_RE.match(line)
        if not m:
            continue
        name = m.group('name')
        labels_str = m.group('labels') or ''
        value_str = m.group('value')

        try:
            value = float(value_str)
        except ValueError:
            continue

        labels = dict(LABEL_RE.findall(labels_str))

        if name not in result:
            result[name] = []
        result[name].append({'labels': labels, 'value': value})

    return result


def extract_metric(parsed: Dict, name: str, label_filter: Dict = None) -> Any:
    """
    Extract a scalar value from parsed metrics.
    If label_filter is given, only return the first matching sample's value.
    """
    samples = parsed.get(name, [])
    for sample in samples:
        if label_filter:
            if all(sample['labels'].get(k) == v for k, v in label_filter.items()):
                return sample['value']
        else:
            return sample['value']
    return None


def flatten_metrics(parsed: Dict) -> Dict[str, Any]:
    """
    Flatten parsed metrics to a simple dict.
    For metrics with labels, create keys like metric_name__label1_val1__label2_val2.
    """
    flat = {}
    for name, samples in parsed.items():
        if len(samples) == 1 and not samples[0]['labels']:
            flat[name] = samples[0]['value']
        else:
            for sample in samples:
                label_part = '__'.join(f"{k}_{v}" for k, v in sample['labels'].items())
                key = f"{name}__{label_part}" if label_part else name
                flat[key] = sample['value']
    return flat
