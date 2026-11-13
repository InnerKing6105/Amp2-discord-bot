import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from advancement_names import AdvancementResolver, humanize_advancement


class AdvancementNameTests(unittest.TestCase):
    def test_friendly_cobbleverse_fallback(self):
        self.assertEqual(humanize_advancement('advancements.cobbleverse.root'), 'Cobbleverse: Root')
        self.assertEqual(humanize_advancement('advancements.cobbleverse.catch_first.title'), 'Cobbleverse: Catch First')

    def test_existing_title_unchanged(self):
        self.assertEqual(AdvancementResolver().resolve('Stone Age'), 'Stone Age')
        self.assertEqual(AdvancementResolver().resolve('A Seedy Place'), 'A Seedy Place')

    def test_mod_jar_translation(self):
        with tempfile.TemporaryDirectory() as td:
            jar = Path(td) / 'cobbleverse.jar'
            with ZipFile(jar, 'w') as z:
                z.writestr('assets/cobbleverse/lang/en_us.json',
                           json.dumps({'advancements.cobbleverse.root': 'A New Adventure'}))
            resolver = AdvancementResolver([td])
            self.assertEqual(resolver.resolve('advancements.cobbleverse.root'), 'A New Adventure')

    def test_translation_key_with_title_suffix(self):
        with tempfile.TemporaryDirectory() as td:
            lang = Path(td) / 'en_us.json'
            lang.write_text(json.dumps({'advancements.cobbleverse.root.title': 'The True Title'}))
            self.assertEqual(AdvancementResolver([lang]).resolve('advancements.cobbleverse.root'), 'The True Title')

    def test_mod_dir_translation(self):
        with tempfile.TemporaryDirectory() as td:
            lang = Path(td) / 'assets' / 'cobbleverse' / 'lang' / 'en_us.json'
            lang.parent.mkdir(parents=True)
            lang.write_text(json.dumps({'advancements.cobbleverse.root': 'The Journey Begins'}))
            resolver = AdvancementResolver([td])
            self.assertEqual(resolver.resolve('advancements.cobbleverse.root'), 'The Journey Begins')

    def test_mod_json_title_by_resource_id(self):
        with tempfile.TemporaryDirectory() as td:
            pack = Path(td) / 'pack.zip'
            with ZipFile(pack, 'w') as z:
                z.writestr('data/cobbleverse/advancement/root.json',
                           json.dumps({'display': {'title': {'text': 'Exploring the World'}}}))
            resolver = AdvancementResolver([td])
            self.assertEqual(resolver.resolve('cobbleverse:root'), 'Exploring the World')
            self.assertEqual(resolver.resolve('advancements.cobbleverse.root'), 'Exploring the World')

    def test_mod_json_title_from_translation(self):
        with tempfile.TemporaryDirectory() as td:
            pack = Path(td) / 'pack.jar'
            with ZipFile(pack, 'w') as z:
                z.writestr('assets/cobbleverse/lang/en_us.json',
                           json.dumps({'advancements.cobbleverse.root': 'Official Name'}))
                z.writestr('data/cobbleverse/advancements/root.json',
                           json.dumps({'display': {'title': {'translate': 'advancements.cobbleverse.root'}}}))
            resolver = AdvancementResolver([pack])
            self.assertEqual(resolver.resolve('cobbleverse:root'), 'Official Name')

    def test_private_override_prioritized(self):
        with tempfile.TemporaryDirectory() as td:
            lang = Path(td) / 'en_us.json'
            lang.write_text(json.dumps({'advancements.cobbleverse.root': 'Pack Value'}))
            overrides = Path(td) / 'advancement_names.json'
            overrides.write_text(json.dumps({'advancements.cobbleverse.root': 'My Custom Name'}))
            resolver = AdvancementResolver([lang], overrides)
            self.assertEqual(resolver.resolve('advancements.cobbleverse.root'), 'My Custom Name')

    def test_missing_or_broken_files_do_not_crash(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / 'broken.jar'
            bad.write_text('not a zip')
            resolver = AdvancementResolver([bad, Path(td) / 'does-not-exist'])
            self.assertEqual(resolver.resolve('advancements.example.root'), 'Example: Root')

    def test_garbage_and_control_characters(self):
        with tempfile.TemporaryDirectory() as td:
            lang = Path(td) / 'en_us.json'
            lang.write_text(json.dumps({'key': 'Hi\nthere\x00'}))
            resolver = AdvancementResolver([lang])
            self.assertEqual(resolver.resolve('key'), 'Hi there')

    def test_no_untrusted_code_execution(self):
        self.assertEqual(AdvancementResolver().resolve('advancements.some_mod.main_path'), 'Some Mod: Main Path')


if __name__ == '__main__':
    unittest.main()
