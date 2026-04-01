from django.contrib import admin
from .models import InverterSnapshot


@admin.register(InverterSnapshot)
class InverterSnapshotAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'connected', 'battery_soc', 'battery_voltage', 'load_power']
    list_filter = ['connected']
    readonly_fields = ['timestamp']
