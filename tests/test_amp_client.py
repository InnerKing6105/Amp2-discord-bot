import unittest
from unittest.mock import Mock, patch
from amp_client import AMPClient, AMPError


class AmpTests(unittest.TestCase):
    def test_working_ads_proxy_route(self):
        client = AMPClient('http://127.0.0.1:8080', 'x', 'y', 'a1b2c3d4')
        self.assertEqual(client.api_url, 'http://127.0.0.1:8080/API/ADSModule/Servers/a1b2c3d4/API')

    def test_direct_instance_route(self):
        self.assertEqual(AMPClient('http://127.0.0.1:8081', 'x', 'y').api_url,
                         'http://127.0.0.1:8081/API')

    def test_dashboard_url_rejected(self):
        with self.assertRaises(AMPError):
            AMPClient('http://127.0.0.1:8080/instances/a1b2c3d4/status', 'x', 'y')

    def test_login_and_updates_same_session(self):
        client = AMPClient('http://127.0.0.1:8080', 'user', 'pass', 'abc')
        calls = []
        def fake_post(method, payload):
            calls.append((method, payload.copy()))
            if method == 'Core/Login':
                return {'success': True, 'sessionID': 'stub-session'}
            if method == 'Core/GetUpdates':
                return {'ConsoleEntries': []}
            return {'State': 20}
        client._post = fake_post
        client.updates()
        client.status()
        self.assertEqual([m for m, _ in calls], ['Core/Login', 'Core/GetUpdates', 'Core/GetStatus'])
        self.assertEqual(calls[1][1]['SESSIONID'], 'stub-session')
        self.assertEqual(calls[2][1]['SESSIONID'], 'stub-session')


if __name__ == '__main__':
    unittest.main()
