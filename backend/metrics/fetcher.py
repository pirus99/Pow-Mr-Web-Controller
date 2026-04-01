"""
Fetches Prometheus metrics from Solax and Battery endpoints.
Provides a cached view of the last successful scrape.
"""
import logging
import threading
import time
from typing import Dict, Any, Optional

import requests
from django.conf import settings

from .prometheus_parser import parse_prometheus_text

logger = logging.getLogger(__name__)

_cache_lock = threading.Lock()
_cache: Dict[str, Any] = {
    'solax': {'data': None, 'last_scraped': None, 'error': None},
    'battery': {'data': None, 'last_scraped': None, 'error': None},
}


def _fetch_url(url: str, timeout: int) -> Optional[str]:
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def _scrape(source: str, url: str) -> None:
    text = _fetch_url(url, settings.EXTERNAL_METRICS_TIMEOUT)
    with _cache_lock:
        if text is None:
            _cache[source]['error'] = f'Failed to fetch from {url}'
        else:
            _cache[source]['data'] = parse_prometheus_text(text)
            _cache[source]['last_scraped'] = time.time()
            _cache[source]['error'] = None


def get_solax_metrics() -> Dict[str, Any]:
    """Fetch (or return cached) Solax metrics. Always re-fetches."""
    _scrape('solax', settings.SOLAX_METRICS_URL)
    with _cache_lock:
        return dict(_cache['solax'])


def get_battery_metrics() -> Dict[str, Any]:
    """Fetch (or return cached) Battery metrics. Always re-fetches."""
    _scrape('battery', settings.BATTERY_METRICS_URL)
    with _cache_lock:
        return dict(_cache['battery'])


def get_cached_solax() -> Dict[str, Any]:
    with _cache_lock:
        return dict(_cache['solax'])


def get_cached_battery() -> Dict[str, Any]:
    with _cache_lock:
        return dict(_cache['battery'])
