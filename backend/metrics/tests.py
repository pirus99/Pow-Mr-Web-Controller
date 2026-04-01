from django.test import TestCase
from .prometheus_parser import parse_prometheus_text, extract_metric, flatten_metrics

SAMPLE_TEXT = """# HELP solax_grid_power_watts Inverter AC Output Power
# TYPE solax_grid_power_watts gauge
solax_grid_power_watts{inverter="garage"} 659.0
solax_grid_power_watts{inverter="huette"} 167.0
# HELP solax_feedin_power_watts Grid Feed-in Power
# TYPE solax_feedin_power_watts gauge
solax_feedin_power_watts{inverter="garage"} -479.0
# HELP daly_bms_soc_percent State of charge (%)
# TYPE daly_bms_soc_percent gauge
daly_bms_soc_percent{instance="bms0",model="Daly BMS"} 96.3
"""


class PrometheusParserTest(TestCase):

    def test_parse_basic(self):
        parsed = parse_prometheus_text(SAMPLE_TEXT)
        self.assertIn('solax_grid_power_watts', parsed)
        self.assertEqual(len(parsed['solax_grid_power_watts']), 2)

    def test_label_extraction(self):
        parsed = parse_prometheus_text(SAMPLE_TEXT)
        samples = parsed['solax_grid_power_watts']
        garage = next(s for s in samples if s['labels']['inverter'] == 'garage')
        self.assertAlmostEqual(garage['value'], 659.0)

    def test_extract_metric_with_labels(self):
        parsed = parse_prometheus_text(SAMPLE_TEXT)
        val = extract_metric(parsed, 'solax_feedin_power_watts', {'inverter': 'garage'})
        self.assertAlmostEqual(val, -479.0)

    def test_extract_metric_no_labels(self):
        parsed = parse_prometheus_text(SAMPLE_TEXT)
        val = extract_metric(parsed, 'daly_bms_soc_percent')
        self.assertAlmostEqual(val, 96.3)

    def test_extract_nonexistent(self):
        parsed = parse_prometheus_text(SAMPLE_TEXT)
        val = extract_metric(parsed, 'nonexistent_metric')
        self.assertIsNone(val)

    def test_flatten_metrics(self):
        parsed = parse_prometheus_text(SAMPLE_TEXT)
        flat = flatten_metrics(parsed)
        self.assertIn('solax_feedin_power_watts__inverter_garage', flat)
        self.assertAlmostEqual(flat['solax_feedin_power_watts__inverter_garage'], -479.0)

    def test_comments_ignored(self):
        text = "# HELP foo A metric\n# TYPE foo gauge\nfoo 42.0\n"
        parsed = parse_prometheus_text(text)
        self.assertIn('foo', parsed)
        self.assertAlmostEqual(parsed['foo'][0]['value'], 42.0)

    def test_scientific_notation(self):
        text = "some_counter 3.092635e+06\n"
        parsed = parse_prometheus_text(text)
        self.assertIn('some_counter', parsed)
        self.assertAlmostEqual(parsed['some_counter'][0]['value'], 3092635.0)
