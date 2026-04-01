from django.db import models


class InverterSnapshot(models.Model):
    """Periodic snapshot of inverter readings for history tracking."""
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Measurements
    ac_voltage = models.FloatField(null=True)
    ac_frequency = models.FloatField(null=True)
    pv_voltage = models.FloatField(null=True)
    battery_voltage = models.FloatField(null=True)
    battery_soc = models.IntegerField(null=True)
    battery_charge_current = models.FloatField(null=True)
    battery_discharge_current = models.FloatField(null=True)
    load_voltage = models.FloatField(null=True)
    load_frequency = models.FloatField(null=True)
    load_power = models.IntegerField(null=True)
    load_va = models.IntegerField(null=True)
    load_percent = models.IntegerField(null=True)

    # Settings at time of snapshot
    output_source_priority = models.IntegerField(null=True)
    charger_source_priority = models.IntegerField(null=True)
    max_utility_charge_current = models.IntegerField(null=True)
    charger_status = models.IntegerField(null=True)

    connected = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Snapshot @ {self.timestamp} (connected={self.connected})"
