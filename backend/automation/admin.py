from django.contrib import admin
from .models import AutomationRule, AutomationLog


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'enabled', 'metric_source', 'metric_name', 'operator', 'threshold', 'last_triggered']
    list_filter = ['enabled', 'metric_source']
    list_editable = ['enabled']


@admin.register(AutomationLog)
class AutomationLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'rule', 'action', 'metric_value', 'message']
    list_filter = ['action', 'rule']
    readonly_fields = ['timestamp', 'rule', 'action', 'message', 'metric_value']
