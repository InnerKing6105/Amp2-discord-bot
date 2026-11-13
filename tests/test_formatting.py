import unittest
from formatting import (format_uptime, metric_display, metric_percent, player_count,
                        players_from_api, pretty_state, safe_text, state_code)


class FormattingTests(unittest.TestCase):
    def test_online(self):
        self.assertEqual(pretty_state({'State': 20}), 'Online')
        self.assertEqual(pretty_state({'State': '20'}), 'Online')
        self.assertEqual(state_code({'State': 'bad'}), None)

    def test_metric_unavailable(self):
        self.assertEqual(metric_display({}, 'cpu'), 'Not available')

    def test_metric_cpu_percent(self):
        status = {'Metrics': {'CPU Usage': {'RawValue': 15.6, 'Units': '%', 'Percent': 15.6}}}
        self.assertEqual(metric_display(status, 'cpu'), '15.6 %')
        self.assertEqual(metric_percent(status, 'cpu'), 15.6)

    def test_metrics_gone(self):
        self.assertIsNone(metric_percent({'Metrics': {'RAM Usage': {'RawValue': 2048, 'Units': 'MB'}}}, 'ram'))

    def test_uptime(self):
        self.assertEqual(format_uptime(3660), '1h 1m')
        self.assertEqual(format_uptime(90060), '1d 1h 1m')
        self.assertEqual(format_uptime(None), 'Not available')

    def test_player_formats(self):
        self.assertEqual(players_from_api({'uuid1': 'Steve', 'uuid2': 'Alex'}), ['Alex', 'Steve'])
        self.assertEqual(players_from_api({'uuid1': {'Name': 'Steve'}}), ['Steve'])
        self.assertEqual(players_from_api([{'name': 'Alex'}, {'name': 'Alex'}]), ['Alex'])
        self.assertEqual(players_from_api({'Result': [{'Name': 'Steve'}]}), ['Steve'])
        self.assertEqual(players_from_api({'Status': False, 'Reason': 'not allowed'}), [])

    def test_player_count(self):
        self.assertEqual(player_count({'ActiveUsers': 4, 'MaxUsers': 20}), ('4', '20'))
        self.assertEqual(player_count({}, []), ('0', '—'))
        self.assertEqual(player_count({}, None), ('Not available', '—'))

    def test_message_sanitization(self):
        self.assertEqual(safe_text('@everyone\n`hack`'), '@\u200beveryone \'hack\'')


if __name__ == '__main__':
    unittest.main()
