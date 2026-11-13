import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from bridge_identity import (avatar_url, discord_minecraft_name,
                             load_avatar_overrides, valid_avatar_identifier, minecraft_chat_command)


class MinecraftIdentityTests(unittest.TestCase):
    def test_plain_username_always_wins_over_fancy_display_name(self):
        author = SimpleNamespace(name='exampleuser', display_name='ᴅɪsᴄᴏʀᴅ', id=123)
        self.assertEqual(discord_minecraft_name(author), 'exampleuser')

    def test_unicode_display_name_does_not_become_discord_user(self):
        author = SimpleNamespace(name='exampleuser', display_name='ᴅɪsᴄᴏʀᴅ', id=123)
        text = discord_minecraft_name(author, 'display')
        self.assertNotEqual(text, 'Discord user')
        self.assertIn('ᴅ', text)

    def test_trick_username_control_chars_are_cleaned(self):
        author = SimpleNamespace(name='bad\n§x\u202e', display_name='', id=123)
        self.assertEqual(discord_minecraft_name(author), 'badx')

    def test_use_id_when_no_name(self):
        author = SimpleNamespace(name='', display_name='‼', id=123)
        self.assertEqual(discord_minecraft_name(author), 'User-123')

    def test_minecraft_tellraw_uses_real_username_and_keeps_payload_safe(self):
        author = SimpleNamespace(name='exampleuser', display_name='ᴅɪsᴄᴏʀᴅ', id=123)
        command = minecraft_chat_command(author, 'hello; /op Steve')
        self.assertTrue(command.startswith('tellraw @a '))
        payload = json.loads(command.split(' ', 2)[2])
        self.assertEqual(payload['extra'][1]['text'], 'exampleuser')
        self.assertEqual(payload['extra'][3]['text'], 'hello; /op Steve')
        self.assertNotIn('Discord user', command)

    def test_skin_url_by_java_username(self):
        self.assertEqual(avatar_url('ExampleUser'), 'https://mc-heads.net/avatar/ExampleUser/96.png')

    def test_skin_url_by_uuid_override_case_insensitive(self):
        uid = '0123456789abcdef0123456789abcdef'
        self.assertEqual(avatar_url('ExampleUser', {'exampleuser': uid}), f'https://mc-heads.net/avatar/{uid}/96.png')

    def test_skin_url_by_texture(self):
        skin = 'a' * 64
        self.assertTrue(valid_avatar_identifier(skin))
        self.assertEqual(avatar_url('Alex', {'alex': skin}), f'https://mc-heads.net/avatar/{skin}/96.png')

    def test_reject_bad_paths_urls(self):
        self.assertIsNone(avatar_url('../player'))
        self.assertIsNone(avatar_url('a'))
        self.assertIsNone(avatar_url('Player', {'player': 'https://example.com/pic.png'}))

    def test_load_case_insensitive_overrides(self):
        with TemporaryDirectory() as directory:
            p = Path(directory) / 'overrides.json'
            p.write_text(json.dumps({'ExampleUser': '0123456789abcdef0123456789abcdef'}), encoding='utf-8')
            result = load_avatar_overrides(p)
            self.assertIn('exampleuser', result)
            self.assertEqual(avatar_url('EXAMPLEUSER', result),
                             'https://mc-heads.net/avatar/0123456789abcdef0123456789abcdef/96.png')

    def test_invalid_override_rejected(self):
        with TemporaryDirectory() as directory:
            p = Path(directory) / 'overrides.json'
            p.write_text(json.dumps({'Steve': 'http://evil.local/image'}), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_avatar_overrides(p)


if __name__ == '__main__':
    unittest.main()
