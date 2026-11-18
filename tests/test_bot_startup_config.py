"""Regression test for advancement auto-discovery startup configuration."""
import ast
from pathlib import Path
import unittest


class StartupConfigurationTests(unittest.TestCase):
    def test_discovery_options_defined_before_access(self):
        module = ast.parse((Path(__file__).resolve().parents[1] / 'bot.py').read_text(encoding='utf-8'))
        names = {'ADVANCEMENT_AUTO_DISCOVER', 'MINECRAFT_SERVER_ROOT',
                 'AMP_DATASTORE', 'AMP_INSTANCE_FOLDER'}
        assigned = set()
        for node in module.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned.add(target.id)
            elif isinstance(node, ast.If) and any(isinstance(n, ast.Name) and n.id == 'ADVANCEMENT_AUTO_DISCOVER'
                                                  for n in ast.walk(node.test)):
                self.assertTrue(names.issubset(assigned), f'Missing config before first use: {names - assigned}')
                return
        self.fail('Advancement startup discovery block not found')

    def test_discovery_variables_read_real_environment_settings(self):
        module = ast.parse((Path(__file__).resolve().parents[1] / 'bot.py').read_text(encoding='utf-8'))
        names = {'ADVANCEMENT_AUTO_DISCOVER', 'MINECRAFT_SERVER_ROOT',
                 'AMP_DATASTORE', 'AMP_INSTANCE_FOLDER'}
        assignments = [n for n in module.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
        settings = {'ADVANCEMENT_AUTO_DISCOVER':'true', 'MINECRAFT_SERVER_ROOT':r'C:\\Example\\Minecraft',
                    'AMP_DATASTORE':'', 'AMP_INSTANCE_FOLDER':'DIscordbottesting01'}
        scope = {'setting':lambda key, default='': settings.get(key,default),
                 'enabled':lambda key, default='true': settings.get(key,default).lower() in {'1','true','yes','on'}}
        exec(compile(ast.Module(body=assignments, type_ignores=[]), '<bot-config>', 'exec'), scope)
        self.assertTrue(scope['ADVANCEMENT_AUTO_DISCOVER'])
        self.assertEqual(scope['AMP_INSTANCE_FOLDER'], 'DIscordbottesting01')
        self.assertEqual(scope['AMP_DATASTORE'], '')
        self.assertTrue(scope['MINECRAFT_SERVER_ROOT'])


if __name__ == '__main__':
    unittest.main()
