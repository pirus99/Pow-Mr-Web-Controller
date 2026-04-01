"""
Automation rule models.

A Rule has:
  - A Condition (metric name, operator, threshold, duration)
  - An Action (write a register value)
  - An inverse/reset action (optional)
"""
from django.db import models


class AutomationRule(models.Model):
    """
    Defines an automation rule that monitors a metric and controls the inverter.

    Example:
      If solax_feedin_power_watts{inverter="garage"} > 400 for 60s
      → set output_source_priority = 0 (Utility First)
    """

    METRIC_SOURCES = [
        ('solax', 'Solax Inverter'),
        ('battery', 'Battery BMS'),
        ('powmr', 'PowMr Inverter'),
    ]

    OPERATORS = [
        ('>', 'Greater than'),
        ('>=', 'Greater than or equal'),
        ('<', 'Less than'),
        ('<=', 'Less than or equal'),
        ('==', 'Equal'),
        ('!=', 'Not equal'),
    ]

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)

    # Condition
    metric_source = models.CharField(max_length=20, choices=METRIC_SOURCES, default='solax')
    metric_name = models.CharField(max_length=200, help_text='Prometheus metric name, e.g. solax_feedin_power_watts')
    metric_labels = models.JSONField(
        default=dict,
        blank=True,
        help_text='Label filters as JSON, e.g. {"inverter": "garage"}',
    )
    operator = models.CharField(max_length=2, choices=OPERATORS, default='>')
    threshold = models.FloatField(help_text='Numeric threshold to compare against')
    duration_seconds = models.IntegerField(
        default=0,
        help_text='How long the condition must be true before firing (seconds)',
    )

    # Action (register write)
    action_register = models.CharField(
        max_length=100,
        help_text='PowMr register name to write, e.g. output_source_priority',
    )
    action_value = models.IntegerField(help_text='Value to write to the register')

    # Optional reset action when condition becomes false
    reset_register = models.CharField(max_length=100, blank=True, default='')
    reset_value = models.IntegerField(null=True, blank=True)
    reset_duration_seconds = models.IntegerField(
        default=0,
        help_text='How long condition must be false before resetting',
    )

    # Runtime state (not exposed in detail serializer, used internally)
    condition_met_since = models.DateTimeField(null=True, blank=True)
    condition_clear_since = models.DateTimeField(null=True, blank=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    last_reset = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class AutomationLog(models.Model):
    """Log of rule firings."""

    ACTIONS = [
        ('triggered', 'Triggered'),
        ('reset', 'Reset'),
        ('error', 'Error'),
    ]

    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=20, choices=ACTIONS)
    message = models.TextField(blank=True)
    metric_value = models.FloatField(null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.rule.name} – {self.action} @ {self.timestamp}"
