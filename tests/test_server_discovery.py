import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from advancement_names import AdvancementResolver
from server_discovery import (find_minecraft_root, asset_paths_for_root,
                              discover_advancement_paths)


class AutoDiscoveryTests(unittest.TestCase):
    def make_instance(self, datastore, name, world='world'):
        minecraft = datastore / 'Instances' / name / 'Minecraft'
        minecraft.mkdir(parents=True)
        (minecraft / 'server.properties').write_text(f'# AMP Minecraft\nlevel-name={world}\n')
        (minecraft / 'mods').mkdir()
        (minecraft / world / 'datapacks').mkdir(parents=True)
        return minecraft

    def test_unique_instance_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'AMPDatastore'
            expected = self.make_instance(store, 'TestServer')
            found, status = find_minecraft_root(search_roots=[store])
            self.assertEqual(found, expected)
            self.assertEqual(status, 'auto')

    def test_multiple_instances_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'AMPDatastore'
            self.make_instance(store, 'Server1')
            self.make_instance(store, 'Server2')
            found, status = find_minecraft_root(search_roots=[store])
            self.assertIsNone(found)
            self.assertIn('ambiguous', status)

    def test_instance_hint_selects_one_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'AMPDatastore'
            self.make_instance(store, 'OtherServer')
            expected = self.make_instance(store, 'DIscordbottesting01')
            found, status = find_minecraft_root(instance_hint='discordbottesting01', search_roots=[store])
            self.assertEqual(found, expected)
            self.assertIn('match', status)

    def test_world_name_from_server_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'AMPDatastore'
            root = self.make_instance(store, 'MyServer', 'The_Nether_Reborn')
            self.assertIn(root / 'The_Nether_Reborn' / 'datapacks', asset_paths_for_root(root))
            self.assertNotIn(root / 'world' / 'datapacks', asset_paths_for_root(root))

    def test_explicit_root_overrides_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'AMPDatastore'
            first = self.make_instance(store, 'One')
            self.make_instance(store, 'Two')
            selected, status = find_minecraft_root(str(first), search_roots=[store])
            self.assertEqual(selected, first)
            self.assertEqual(status, 'explicit')

    def test_bad_explicit_root_does_not_pick_other_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'AMPDatastore'
            self.make_instance(store, 'One')
            selected, status = find_minecraft_root(str(Path(tmp)/'missing'), search_roots=[store])
            self.assertIsNone(selected)
            self.assertIn('missing', status)

    def test_registry_style_instances_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'AMPDatastore'
            expected = self.make_instance(store, 'ServerOne')
            selected, _ = find_minecraft_root(search_roots=[store / 'Instances'])
            self.assertEqual(selected, expected)

    def test_auto_discovered_title_description_from_mod_and_datapack(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'AMPDatastore'
            root = self.make_instance(store, 'Mineverse', 'CobbleWorld')
            with ZipFile(root / 'mods' / 'cobbleverse.jar', 'w') as jar:
                jar.writestr('assets/cobbleverse/lang/en_us.json', json.dumps({
                    'advancements.cobbleverse.root.title': 'New Horizons',
                    'advancements.cobbleverse.root.description': 'Begin your adventure!',
                }))
            with ZipFile(root / 'CobbleWorld' / 'datapacks' / 'custom.zip', 'w') as pack:
                pack.writestr('data/cobbleverse/advancement/root.json', json.dumps({
                    'display': {'title': {'translate': 'advancements.cobbleverse.root.title'},
                                'description': {'translate': 'advancements.cobbleverse.root.description'}},
                }))
            paths, status = discover_advancement_paths(search_roots=[store])
            resolver = AdvancementResolver(paths)
            info = resolver.resolve_info('advancements.cobbleverse.root')
            self.assertEqual(info.title, 'New Horizons')
            self.assertEqual(info.description, 'Begin your adventure!')
            self.assertTrue(info.official)

    def test_description_from_direct_english_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'en_us.json').write_text(json.dumps({
                'advancements.cobbleverse.root': 'Cobbleverse!',
                'advancements.cobbleverse.root.desc': 'Meet many Pokémon.'
            }))
            details = AdvancementResolver([folder]).resolve_info('advancements.cobbleverse.root')
            self.assertEqual(details.title, 'Cobbleverse!')
            self.assertEqual(details.description, 'Meet many Pokémon.')

    def test_literal_json_title_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / 'pack.zip'
            with ZipFile(pack, 'w') as z:
                z.writestr('data/adventures/advancement/first.json', json.dumps({
                    'display': {'title': {'text': 'First Steps'},
                                'description': {'text': 'Start exploring!'}}
                }))
            details = AdvancementResolver([pack]).resolve_info('adventures:first')
            self.assertEqual(details.title, 'First Steps')
            self.assertEqual(details.description, 'Start exploring!')

    def test_nonexistent_explicit_path_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, status = discover_advancement_paths([str(Path(tmp) / 'missing')], search_roots=[Path(tmp)])
            self.assertEqual(paths, [])
            self.assertIn('no AMP', status)

    def test_text_component_translation_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / 'pack.zip'
            with ZipFile(pack, 'w') as z:
                z.writestr('data/demo/advancement/first.json', json.dumps({
                    'display': {'title': {'translate': 'demo.missing', 'fallback': 'A Real Title'},
                                'description': {'text': 'Find ', 'extra': [{'text': 'a secret'}]}}
                }))
            info = AdvancementResolver([pack]).resolve_info('demo:first')
            self.assertEqual(info.title, 'A Real Title')
            self.assertEqual(info.description, 'Find a secret')

if __name__ == '__main__':
    unittest.main()
