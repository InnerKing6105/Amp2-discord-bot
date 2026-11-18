import unittest

from event_routing import event_channel_id


class EventRoutingTests(unittest.TestCase):
    def test_chat_stays_in_chat(self):
        self.assertEqual(event_channel_id('chat', 10, 20), 10)

    def test_player_events_use_dedicated_channel(self):
        for kind in ('join', 'leave', 'death'):
            with self.subTest(kind=kind):
                self.assertEqual(event_channel_id(kind, 10, 20), 20)

    def test_advancements_remain_in_chat(self):
        self.assertEqual(event_channel_id('advancement', 10, 20), 10)

    def test_old_config_still_works_without_channel(self):
        for kind in ('join', 'leave', 'death', 'advancement'):
            with self.subTest(kind=kind):
                self.assertEqual(event_channel_id(kind, 10), 10)

    def test_disabling_events_preserves_chat(self):
        self.assertEqual(event_channel_id('chat', 10, 20, False), 10)
        for kind in ('join', 'leave', 'death', 'advancement'):
            with self.subTest(kind=kind):
                self.assertIsNone(event_channel_id(kind, 10, 20, False))

    def test_unknown_types_are_ignored(self):
        self.assertIsNone(event_channel_id('console', 10, 20))
        self.assertIsNone(event_channel_id('crash', 10, 20))


if __name__ == '__main__':
    unittest.main()
