"""
Automation rules evaluation engine.

Called periodically by a background thread to:
1. Fetch the current metric value for each enabled rule.
2. Evaluate the condition.
3. If condition has been true for duration_seconds → fire the action.
4. If condition is false and reset is configured → fire the reset action.
"""
import logging
import operator as op
import threading
import time
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

_engine_thread = None
_stop_event = threading.Event()

OPERATORS = {
    '>': op.gt,
    '>=': op.ge,
    '<': op.lt,
    '<=': op.le,
    '==': op.eq,
    '!=': op.ne,
}

POLL_INTERVAL = 10  # seconds between rule evaluations


def _get_metric_value(rule):
    """Return the current float value of the metric for the given rule, or None."""
    from metrics.fetcher import get_cached_solax, get_cached_battery
    from metrics.prometheus_parser import extract_metric
    from inverter.modbus_client import read_inverter_status

    if rule.metric_source == 'solax':
        result = get_cached_solax()
        data = result.get('data') or {}
    elif rule.metric_source == 'battery':
        result = get_cached_battery()
        data = result.get('data') or {}
    elif rule.metric_source == 'powmr':
        inv = read_inverter_status()
        if inv is None:
            return None
        # Map powmr metric names to status fields
        return inv.get(rule.metric_name)
    else:
        return None

    label_filter = rule.metric_labels if rule.metric_labels else None
    return extract_metric(data, rule.metric_name, label_filter)


def _evaluate_condition(current_value, operator_str, threshold):
    """Evaluate operator(current_value, threshold). Returns bool or None."""
    if current_value is None:
        return None
    fn = OPERATORS.get(operator_str)
    if fn is None:
        return None
    try:
        return fn(float(current_value), float(threshold))
    except (TypeError, ValueError):
        return None


def _evaluate_rule(rule):
    """Evaluate one rule and fire actions if needed."""
    from inverter.modbus_client import write_register
    from .models import AutomationLog

    current_value = _get_metric_value(rule)
    condition_result = _evaluate_condition(current_value, rule.operator, rule.threshold)

    now = timezone.now()

    if condition_result is None:
        # Cannot evaluate – skip
        logger.debug("Rule '%s': metric '%s' unavailable", rule.name, rule.metric_name)
        return

    if condition_result:
        # Condition is currently true
        rule.condition_clear_since = None

        if rule.condition_met_since is None:
            rule.condition_met_since = now

        met_for = (now - rule.condition_met_since).total_seconds()

        if met_for >= rule.duration_seconds and rule.last_triggered is None:
            # Fire action
            logger.info(
                "Rule '%s' triggered: %s %s %s (value=%.3f, met_for=%.1fs)",
                rule.name, rule.metric_name, rule.operator,
                rule.threshold, current_value, met_for,
            )
            success = write_register(rule.action_register, rule.action_value)
            rule.last_triggered = now
            AutomationLog.objects.create(
                rule=rule,
                action='triggered' if success else 'error',
                message=f'Set {rule.action_register}={rule.action_value}' + ('' if success else ' (FAILED)'),
                metric_value=current_value,
            )
            rule.save(update_fields=[
                'condition_met_since', 'condition_clear_since',
                'last_triggered',
            ])
    else:
        # Condition is currently false
        rule.condition_met_since = None

        if rule.last_triggered is not None:
            # Was previously triggered – check reset condition
            if rule.condition_clear_since is None:
                rule.condition_clear_since = now

            clear_for = (now - rule.condition_clear_since).total_seconds()

            if (
                rule.reset_register
                and rule.reset_value is not None
                and clear_for >= rule.reset_duration_seconds
                and rule.last_reset != rule.last_triggered  # haven't reset for this trigger
            ):
                logger.info(
                    "Rule '%s' reset: %s %s %s (value=%.3f, clear_for=%.1fs)",
                    rule.name, rule.metric_name, rule.operator,
                    rule.threshold, current_value, clear_for,
                )
                success = write_register(rule.reset_register, rule.reset_value)
                rule.last_reset = now
                AutomationLog.objects.create(
                    rule=rule,
                    action='reset' if success else 'error',
                    message=f'Reset {rule.reset_register}={rule.reset_value}' + ('' if success else ' (FAILED)'),
                    metric_value=current_value,
                )
                rule.save(update_fields=[
                    'condition_met_since', 'condition_clear_since',
                    'last_triggered', 'last_reset',
                ])

        if rule.condition_clear_since is None:
            rule.condition_clear_since = now
            rule.save(update_fields=['condition_met_since', 'condition_clear_since'])


def _run_engine():
    """Main loop: refresh external metrics and evaluate all enabled rules."""
    from metrics.fetcher import get_solax_metrics, get_battery_metrics
    from .models import AutomationRule

    logger.info("Automation engine started (poll interval %ds)", POLL_INTERVAL)

    while not _stop_event.is_set():
        try:
            # Pre-fetch external metrics so rules can use cached values
            get_solax_metrics()
            get_battery_metrics()

            rules = AutomationRule.objects.filter(enabled=True)
            for rule in rules:
                try:
                    _evaluate_rule(rule)
                except Exception as exc:
                    logger.error("Error evaluating rule '%s': %s", rule.name, exc)
        except Exception as exc:
            logger.error("Automation engine error: %s", exc)

        _stop_event.wait(POLL_INTERVAL)

    logger.info("Automation engine stopped")


def start_engine():
    global _engine_thread
    if _engine_thread is not None and _engine_thread.is_alive():
        return
    _stop_event.clear()
    _engine_thread = threading.Thread(target=_run_engine, daemon=True, name='automation-engine')
    _engine_thread.start()


def stop_engine():
    _stop_event.set()
