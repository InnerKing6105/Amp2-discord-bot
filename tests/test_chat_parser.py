import unittest
from chat_parser import parse_entry


class ChatTests(unittest.TestCase):
    def test_amp_chat(self):
        self.assertEqual(parse_entry({'Type': 'Chat', 'Source': 'Alex_12', 'Contents': 'hello'}),
                         ('chat', 'Alex_12', 'hello'))

    def test_vanilla(self):
        self.assertEqual(parse_entry({'Type': 'Console', 'Contents': '[12:00:00] [Server thread/INFO]: <Steve> Hi everyone'}),
                         ('chat', 'Steve', 'Hi everyone'))

    def test_join_leave(self):
        self.assertEqual(parse_entry({'Contents': '[Server thread/INFO]: Steve joined the game'}), ('join', 'Steve', ''))
        self.assertEqual(parse_entry({'Contents': '[Server thread/INFO]: Steve left the game'}), ('leave', 'Steve', ''))

    def test_death(self):
        evt = parse_entry({'Contents': '[12:00] [Server thread/INFO]: Steve was slain by Zombie'})
        self.assertEqual(evt[0], 'death')
        self.assertEqual(evt[1], 'Steve')
        self.assertIn('was slain by Zombie', evt[2])

    def test_advancement(self):
        self.assertEqual(parse_entry({'Contents': '[12:00] [Server thread/INFO]: Steve has made the advancement [Stone Age]'}),
                         ('advancement', 'Steve', 'Stone Age'))

    def test_crash(self):
        self.assertEqual(parse_entry({'Contents': 'Encountered an unexpected exception'})[0], 'crash')

    def test_log_noise(self):
        self.assertIsNone(parse_entry({'Type': 'Console', 'Contents': '[Server thread/INFO]: Done (2.5s)!'}))
        self.assertIsNone(parse_entry({'Type': 'Chat', 'Source': '../bad!', 'Contents': 'hello'}))


if __name__ == '__main__':
    unittest.main()
