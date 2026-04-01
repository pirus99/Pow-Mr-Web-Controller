import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .modbus_client import (
    CHARGER_SOURCE_PRIORITY,
    OUTPUT_SOURCE_PRIORITY,
    UTILITY_CHARGE_CURRENT_VALUES,
    WRITE_REGISTERS,
    read_inverter_status,
    write_register,
)
from .serializers import InverterStatusSerializer, WriteRegisterSerializer

logger = logging.getLogger(__name__)


class InverterStatusView(APIView):
    """GET /api/inverter/status – return live inverter metrics."""

    def get(self, request):
        data = read_inverter_status()
        if data is None:
            return Response(
                {
                    'connected': False,
                    'error': 'Could not communicate with inverter. '
                             'Check serial port configuration.',
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        serializer = InverterStatusSerializer(data)
        return Response(serializer.data)


class InverterControlView(APIView):
    """
    POST /api/inverter/control – write a control register.
    Body: {"register": "<name>", "value": <int>}
    """

    def post(self, request):
        serializer = WriteRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reg = serializer.validated_data['register']
        val = serializer.validated_data['value']

        success = write_register(reg, val)
        if not success:
            return Response(
                {'error': f'Failed to write {reg}={val}. Check inverter connection.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'success': True, 'register': reg, 'value': val})


class InverterOptionsView(APIView):
    """GET /api/inverter/options – return valid choices for control registers."""

    def get(self, request):
        return Response({
            'output_source_priority': [
                {'value': k, 'label': v}
                for k, v in OUTPUT_SOURCE_PRIORITY.items()
            ],
            'charger_source_priority': [
                {'value': k, 'label': v}
                for k, v in CHARGER_SOURCE_PRIORITY.items()
            ],
            'utility_charge_current': UTILITY_CHARGE_CURRENT_VALUES,
            'registers': list(WRITE_REGISTERS.keys()),
        })
