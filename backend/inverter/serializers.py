from rest_framework import serializers
from .modbus_client import (
    CHARGER_SOURCE_PRIORITY,
    OUTPUT_SOURCE_PRIORITY,
    UTILITY_CHARGE_CURRENT_VALUES,
    WRITE_REGISTERS,
)


class InverterStatusSerializer(serializers.Serializer):
    """Serializes live inverter status data."""
    connected = serializers.BooleanField()
    ac_voltage = serializers.FloatField(allow_null=True)
    ac_frequency = serializers.FloatField(allow_null=True)
    pv_voltage = serializers.FloatField(allow_null=True)
    battery_voltage = serializers.FloatField(allow_null=True)
    battery_soc = serializers.IntegerField(allow_null=True)
    battery_charge_current = serializers.FloatField(allow_null=True)
    battery_discharge_current = serializers.FloatField(allow_null=True)
    load_voltage = serializers.FloatField(allow_null=True)
    load_frequency = serializers.FloatField(allow_null=True)
    load_power = serializers.IntegerField(allow_null=True)
    load_va = serializers.IntegerField(allow_null=True)
    load_percent = serializers.IntegerField(allow_null=True)
    output_source_priority = serializers.IntegerField(allow_null=True)
    output_source_priority_label = serializers.CharField(allow_null=True)
    charger_source_priority = serializers.IntegerField(allow_null=True)
    charger_source_priority_label = serializers.CharField(allow_null=True)
    max_utility_charge_current = serializers.IntegerField(allow_null=True)
    max_total_charge_current = serializers.IntegerField(allow_null=True)
    on_battery = serializers.BooleanField(allow_null=True)
    ac_active = serializers.BooleanField(allow_null=True)
    load_enabled = serializers.BooleanField(allow_null=True)
    charger_status = serializers.IntegerField(allow_null=True)
    charger_status_label = serializers.CharField(allow_null=True)
    temperature = serializers.IntegerField(allow_null=True)
    bulk_charging_voltage = serializers.FloatField(allow_null=True)
    floating_charging_voltage = serializers.FloatField(allow_null=True)
    low_cutoff_voltage = serializers.FloatField(allow_null=True)
    back_to_utility_voltage = serializers.FloatField(allow_null=True)
    back_to_battery_voltage = serializers.FloatField(allow_null=True)


class WriteRegisterSerializer(serializers.Serializer):
    """Validates a request to write a register value."""
    register = serializers.ChoiceField(choices=list(WRITE_REGISTERS.keys()))
    value = serializers.IntegerField()

    def validate(self, data):
        reg = data['register']
        val = data['value']

        if reg == 'output_source_priority' and val not in OUTPUT_SOURCE_PRIORITY:
            raise serializers.ValidationError(
                f"output_source_priority must be one of {list(OUTPUT_SOURCE_PRIORITY.keys())}"
            )
        if reg == 'charger_source_priority' and val not in CHARGER_SOURCE_PRIORITY:
            raise serializers.ValidationError(
                f"charger_source_priority must be one of {list(CHARGER_SOURCE_PRIORITY.keys())}"
            )
        if reg == 'utility_charge_current' and val not in UTILITY_CHARGE_CURRENT_VALUES:
            raise serializers.ValidationError(
                f"utility_charge_current must be one of {UTILITY_CHARGE_CURRENT_VALUES}"
            )
        return data
