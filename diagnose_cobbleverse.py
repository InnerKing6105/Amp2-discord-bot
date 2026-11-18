"""Read-only lookup of unresolved Cobbleverse advancement names in local assets.

Run: .\\.venv\\Scripts\\python.exe diagnose_cobbleverse.py
Prints only asset filenames and related advancement keys/titles, not credentials.
"""
import os
from pathlib import Path
import re
from zipfile import ZipFile, BadZipFile

from dotenv import load_dotenv
from advancement_names import AdvancementResolver, _read_json_bytes, _details_from_advancement
from server_discovery import discover_advancement_paths

BASE = Path(__file__).resolve().parent
TARGET = 'advancements.cobbleverse.root'
MAX_FILES = 1200
MAX_JSON_BYTES = 2_000_000
MAX_MATCHES = 30


def relevant_lang_key(key):
    k = str(key).lower()
    return 'cobbleverse' in k and ('root' in k or 'start' in k or 'begin' in k)


def relevant_advancement_file(name):
    key = str(name).replace('\\', '/').lower()
    return bool(re.search(r'data/cobbleverse/advancements?/(?:[^/]+/)*root\.json$', key))


def inspect_json(label, filename, raw):
    data = _read_json_bytes(raw)
    if data is None:
        return []
    if str(filename).lower().endswith('/en_us.json') or Path(filename).name.lower()=='en_us.json':
        return [(label, key, str(value)[:160]) for key, value in data.items()
                if isinstance(value, str) and relevant_lang_key(key)][:MAX_MATCHES]
    if relevant_advancement_file(filename):
        display = data.get('display', {})
        if isinstance(display, dict):
            return [(label, 'display.title', str(display.get('title', ''))[:160]),
                    (label, 'display.description', str(display.get('description', ''))[:160])]
    return []


def iter_sources(paths):
    """Scan local jars/zips and plain JSON only, and record the containing file."""
    seen = set()
    count = 0
    for root in paths:
        p = Path(root)
        if not p.exists():
            continue
        files = [p] if p.is_file() else p.rglob('*')
        for file in files:
            if count >= MAX_FILES:
                return
            if not file.is_file() or file.is_symlink() or file.suffix.lower() not in ('.json', '.jar', '.zip'):
                continue
            identity = str(file.resolve()).lower()
            if identity in seen:
                continue
            seen.add(identity)
            count += 1
            if file.suffix.lower() == '.json':
                if file.name.lower() != 'en_us.json' and not relevant_advancement_file(file.as_posix()):
                    continue
                try:
                    if file.stat().st_size <= MAX_JSON_BYTES:
                        yield str(file), file.name, file.read_bytes()
                except OSError:
                    continue
            else:
                try:
                    with ZipFile(file) as z:
                        for entry in z.infolist():
                            path = entry.filename.replace('\\','/')
                            if entry.file_size > MAX_JSON_BYTES:
                                continue
                            if not (re.search(r'(^|/)assets/[^/]+/lang/en_us\.json$',path,re.I)
                                    or relevant_advancement_file(path)):
                                continue
                            try:
                                yield f'{file.name}::{path}', path, z.read(entry)
                            except (RuntimeError, OSError, BadZipFile):
                                continue
                except (OSError, BadZipFile, ValueError):
                    continue


def main():
    load_dotenv(BASE / '.env')
    manual = [v.strip().strip('"') for v in os.getenv('ADVANCEMENT_LANGUAGE_PATHS', '').split(';') if v.strip()]
    auto = os.getenv('ADVANCEMENT_AUTO_DISCOVER','true').lower() in ('1','true','yes','on')
    if auto:
        paths, status = discover_advancement_paths(manual, os.getenv('MINECRAFT_SERVER_ROOT',''),
                os.getenv('AMP_DATASTORE',''), os.getenv('AMP_INSTANCE_FOLDER','') or os.getenv('SERVER_NAME',''))
    else:
        paths, status = manual, 'manual only'
    print('AMP discovery:', status)
    print('Folders scanned:', len(paths))
    for folder in paths:
        print('  ', folder)
    resolver = AdvancementResolver(paths, BASE / 'data' / 'advancement_names.json')
    detail = resolver.resolve_info(TARGET)
    print('Current title:',detail.title,'(matched)' if detail.official else '(fallback)')
    print('Matching entries from source files:')
    found = 0
    for label,filename,raw in iter_sources(paths):
        for source,key,value in inspect_json(label,filename,raw):
            found += 1
            if found <= MAX_MATCHES:
                print(' -',source,'|',key,'=',value)
    if not found:
        print(' None. No matching Cobbleverse root translation or root advancement definition found.')
        print(' Try the client resourcepacks if your installed pack keeps translations there,')
        print(' or use a verified local override in data/advancement_names.json.')
    elif found > MAX_MATCHES:
        print(' (additional matches omitted)')
    print('This diagnostic only reads files; it never changes your Minecraft server.')


if __name__=='__main__':
    main()
