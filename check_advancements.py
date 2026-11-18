"""Read-only local diagnostic for Zygarde achievement discovery."""
from pathlib import Path
import os
from dotenv import load_dotenv
from advancement_names import AdvancementResolver
from server_discovery import discover_advancement_paths

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env')
manual = [v.strip().strip('"') for v in os.getenv('ADVANCEMENT_LANGUAGE_PATHS', '').split(';') if v.strip()]
if os.getenv('ADVANCEMENT_AUTO_DISCOVER', 'true').lower() in ('1', 'true', 'yes', 'on'):
    paths, status = discover_advancement_paths(
        manual, os.getenv('MINECRAFT_SERVER_ROOT', ''),
        os.getenv('AMP_DATASTORE', ''),
        os.getenv('AMP_INSTANCE_FOLDER', '') or os.getenv('SERVER_NAME', ''))
else:
    paths, status = manual, 'manual only'
resolver = AdvancementResolver(paths, BASE / 'data' / 'advancement_names.json')
print('AMP discovery:', status)
print('Folders/files found:', len(paths))
for p in paths:
    print(' -', p)
print('Language keys:', len(resolver.translations), 'Advancement titles:', len(resolver.titles),
      'Advancement descriptions:', len(resolver.descriptions))
for key in ('advancements.cobbleverse.root', 'cobbleverse:root'):
    d = resolver.resolve_info(key)
    print(f'{key} => {d.title}' + (f' | {d.description}' if d.description else '') +
          (' (matched)' if d.official else ' (fallback)'))
