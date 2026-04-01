from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import AutomationRule, AutomationLog
from .engine import _evaluate_condition


class AutomationRuleModelTest(TestCase):

    def setUp(self):
        self.rule = AutomationRule.objects.create(
            name='Test Rule',
            metric_source='solax',
            metric_name='solax_feedin_power_watts',
            metric_labels={'inverter': 'garage'},
            operator='>',
            threshold=400.0,
            duration_seconds=60,
            action_register='output_source_priority',
            action_value=0,
        )

    def test_rule_created(self):
        self.assertEqual(AutomationRule.objects.count(), 1)
        self.assertTrue(self.rule.enabled)

    def test_rule_str(self):
        self.assertEqual(str(self.rule), 'Test Rule')


class EvaluateConditionTest(TestCase):

    def test_greater_than_true(self):
        self.assertTrue(_evaluate_condition(500, '>', 400))

    def test_greater_than_false(self):
        self.assertFalse(_evaluate_condition(300, '>', 400))

    def test_equal(self):
        self.assertTrue(_evaluate_condition(400, '==', 400))

    def test_less_than(self):
        self.assertTrue(_evaluate_condition(-10, '<', 0))

    def test_none_value(self):
        self.assertIsNone(_evaluate_condition(None, '>', 400))

    def test_invalid_operator(self):
        self.assertIsNone(_evaluate_condition(100, '??', 50))


class AutomationRuleAPITest(APITestCase):

    def test_list_rules_empty(self):
        response = self.client.get('/api/automation/rules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_create_rule(self):
        data = {
            'name': 'API Test Rule',
            'metric_source': 'solax',
            'metric_name': 'solax_feedin_power_watts',
            'metric_labels': {'inverter': 'garage'},
            'operator': '>',
            'threshold': 400,
            'duration_seconds': 60,
            'action_register': 'output_source_priority',
            'action_value': 0,
            'reset_duration_seconds': 60,
            'enabled': True,
        }
        response = self.client.post('/api/automation/rules/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AutomationRule.objects.count(), 1)
        self.assertEqual(response.data['name'], 'API Test Rule')

    def test_toggle_rule(self):
        rule = AutomationRule.objects.create(
            name='Toggle Test',
            metric_source='solax',
            metric_name='solax_feedin_power_watts',
            metric_labels={},
            operator='>',
            threshold=100,
            duration_seconds=0,
            action_register='output_source_priority',
            action_value=0,
            enabled=True,
        )
        response = self.client.post(f'/api/automation/rules/{rule.id}/toggle/', {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rule.refresh_from_db()
        self.assertFalse(rule.enabled)
