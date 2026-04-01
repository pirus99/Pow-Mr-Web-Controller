from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status


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
