from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, Mock

from inverter import modbus_client


class InverterOptionsAPITest(APITestCase):

    def test_options_endpoint(self):
        response = self.client.get('/api/inverter/options/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('output_source_priority', response.data)
        self.assertIn('charger_source_priority', response.data)
        self.assertIn('utility_charge_current', response.data)

    def test_control_invalid_register(self):
        response = self.client.post(
            '/api/inverter/control/',
            {'register': 'nonexistent_register', 'value': 0},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_control_invalid_output_priority(self):
        response = self.client.post(
            '/api/inverter/control/',
            {'register': 'output_source_priority', 'value': 99},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_control_invalid_utility_current(self):
        response = self.client.post(
            '/api/inverter/control/',
            {'register': 'utility_charge_current', 'value': 15},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ModbusClientConnectionTest(TestCase):

    def tearDown(self):
        modbus_client._reset_client()

    def test_is_client_connected_checks_common_attributes(self):
        class ClientWithBool:
            connected = True
        class ClientWithMethod:
            def is_socket_open(self):
                return True
        self.assertTrue(modbus_client._is_client_connected(ClientWithBool()))
        self.assertTrue(modbus_client._is_client_connected(ClientWithMethod()))
        self.assertFalse(modbus_client._is_client_connected(None))

    @patch('pymodbus.client.ModbusSerialClient')
    def test_get_client_recreates_disconnected_client(self, mock_serial_client):
        stale_client = Mock()
        stale_client.connected = False
        fresh_client = Mock()
        fresh_client.connect.return_value = True
        mock_serial_client.return_value = fresh_client
        modbus_client._modbus_client = stale_client

        client = modbus_client._get_client()

        stale_client.close.assert_called_once()
        self.assertIs(client, fresh_client)
        mock_serial_client.assert_called_once()

    @patch('pymodbus.client.ModbusSerialClient')
    def test_get_client_returns_none_when_connect_fails(self, mock_serial_client):
        client_instance = Mock()
        client_instance.connect.return_value = False
        mock_serial_client.return_value = client_instance

        client = modbus_client._get_client()

        self.assertIsNone(client)
