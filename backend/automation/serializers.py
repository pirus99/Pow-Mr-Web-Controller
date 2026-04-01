from rest_framework import serializers
from .models import AutomationRule, AutomationLog


class AutomationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRule
        fields = [
            'id', 'name', 'description', 'enabled',
            'metric_source', 'metric_name', 'metric_labels',
            'operator', 'threshold', 'duration_seconds',
            'action_register', 'action_value',
            'reset_register', 'reset_value', 'reset_duration_seconds',
            'last_triggered', 'last_reset',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'last_triggered', 'last_reset', 'created_at', 'updated_at']


class AutomationLogSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True)

    class Meta:
        model = AutomationLog
        fields = ['id', 'rule', 'rule_name', 'timestamp', 'action', 'message', 'metric_value']
        read_only_fields = fields
