import json
import unittest
from diagnose_cobbleverse import inspect_json, relevant_advancement_file, relevant_lang_key

class CobbleverseDiagnosticTests(unittest.TestCase):
    def test_relevant_lang_key(self):
        self.assertTrue(relevant_lang_key('advancements.cobbleverse.root'))
        self.assertTrue(relevant_lang_key('advancements.cobbleverse.root.title'))
        self.assertFalse(relevant_lang_key('item.cobbleverse.stone'))

    def test_advancement_path(self):
        self.assertTrue(relevant_advancement_file('data/cobbleverse/advancement/root.json'))
        self.assertFalse(relevant_advancement_file('data/other/advancement/root.json'))

    def test_lang_report(self):
        b = json.dumps({'advancements.cobbleverse.root.title': 'Press C to Start!', 'item.foo':'Ignore'}).encode()
        matches = inspect_json('pack.jar::en_us', 'assets/cobbleverse/lang/en_us.json', b)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][2], 'Press C to Start!')

    def test_root_definition(self):
        b = json.dumps({'display': {'title': {'translate':'advancements.cobbleverse.root'}}}).encode()
        matches = inspect_json('pack.zip', 'data/cobbleverse/advancement/root.json', b)
        self.assertEqual(matches[0][1], 'display.title')
