"""Resolve Minecraft advancement titles from local language and advancement assets.

Offline and read-only: never downloads packs or modifies Minecraft server files.
"""

import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

_MAX_ASSETS = 600
_MAX_JSON_BYTES = 2_000_000
_LANG_FILE = re.compile(r'(^|/)assets/[^/]+/lang/en_us\.json$', re.IGNORECASE)
_ADV_FILE = re.compile(r'(^|/)data/([^/]+)/advancements?/([^/]+(?:/[^/]+)*)\.json$', re.IGNORECASE)
_KEY = re.compile(r'^[a-z0-9_.:/-]+$')


def _read_json_bytes(data):
    if len(data) > _MAX_JSON_BYTES:
        return None
    try:
        obj = json.loads(data.decode('utf-8-sig'))
        return obj if isinstance(obj, dict) else None
    except (UnicodeDecodeError, ValueError):
        return None


def _clean_title(title):
    if not isinstance(title, str):
        return ''
    title = re.sub(r'[\x00-\x1f\x7f]', ' ', title).strip()
    return title[:160]


def _text_component(value, translations):
    if isinstance(value, str):
        return _clean_title(value)
    if isinstance(value, dict):
        if isinstance(value.get('text'), str):
            return _clean_title(value['text'])
        if isinstance(value.get('translate'), str):
            return _clean_title(translations.get(value['translate'], ''))
    return ''


def _title_from_advancement(data, translations):
    display = data.get('display')
    if isinstance(display, dict):
        return _text_component(display.get('title'), translations)
    return ''


def _advancement_id_from_file(path):
    match = _ADV_FILE.search(path.replace('\\', '/'))
    return (match.group(2).lower() + ':' + match.group(3).lower()) if match else ''


def _iter_assets(paths):
    """Yield only relevant JSON assets and capped archives from explicitly chosen paths."""
    count = 0
    for raw in paths:
        p = Path(raw).expanduser()
        if not p.exists():
            continue
        if p.is_file():
            candidates = [p]
        elif p.is_dir():
            # Only look for language JSON, advancement JSON, and .jar/.zip archives.
            candidates = (q for q in p.rglob('*') if q.is_file() and not q.is_symlink()
                          and (q.suffix.lower() in {'.jar', '.zip'}
                               or (q.suffix.lower() == '.json'
                                   and (_LANG_FILE.search(q.as_posix()) or _ADV_FILE.search(q.as_posix())))))
        else:
            continue
        for candidate in candidates:
            if count >= _MAX_ASSETS:
                return
            name = candidate.as_posix()
            ext = candidate.suffix.lower()
            if ext == '.json':
                if candidate.name.lower() == 'en_us.json' or _ADV_FILE.search(name):
                    count += 1
                    try:
                        if candidate.stat().st_size <= _MAX_JSON_BYTES:
                            yield name, candidate.read_bytes()
                    except OSError:
                        continue
            elif ext in {'.jar', '.zip'}:
                count += 1
                try:
                    with ZipFile(candidate) as archive:
                        for info in archive.infolist():
                            entry = info.filename.replace('\\', '/')
                            if info.file_size > _MAX_JSON_BYTES or not (_LANG_FILE.search(entry) or _ADV_FILE.search(entry)):
                                continue
                            try:
                                yield entry, archive.read(info)
                            except (OSError, RuntimeError, BadZipFile):
                                continue
                except (OSError, BadZipFile, ValueError):
                    continue


def humanize_advancement(value):
    """Readable fallback (not claimed to be the mod's official translation)."""
    text = str(value or '').strip().strip('[]')
    if not text:
        return 'Unknown advancement'
    if not _KEY.fullmatch(text):
        return _clean_title(text)
    if text.startswith('advancements.'):
        parts = text.split('.')[1:]
        if len(parts) >= 2:
            namespace = parts.pop(0)
            if len(parts) > 1 and parts[-1] in {'title', 'name'}:
                parts.pop()
            return f'{_words(namespace)}: {_words(" ".join(parts))}'
    if ':' in text:
        namespace, path = text.split(':', 1)
        return f'{_words(namespace)}: {_words(path)}'
    return _words(text)


def _words(text):
    return re.sub(r'\s+', ' ', str(text).replace('_', ' ').replace('-', ' ').replace('/', ' ').replace('.', ' ')).strip().title()


class AdvancementResolver:
    """Cached names; restart Zygarde to reread assets after a modpack update."""

    def __init__(self, asset_paths=(), overrides_file=None):
        self.translations = {}
        self.titles = {}
        self.overrides = {}
        json_assets = []
        for filename, data in _iter_assets(asset_paths):
            obj = _read_json_bytes(data)
            if obj is None:
                continue
            if filename.lower().endswith('/en_us.json') or Path(filename).name.lower() == 'en_us.json':
                for k, v in obj.items():
                    if isinstance(k, str) and isinstance(v, str):
                        self.translations[k] = _clean_title(v)
            elif _advancement_id_from_file(filename):
                json_assets.append((filename, obj))
        for filename, obj in json_assets:
            title = _title_from_advancement(obj, self.translations)
            if title:
                self.titles[_advancement_id_from_file(filename)] = title
        if overrides_file:
            try:
                data = _read_json_bytes(Path(overrides_file).read_bytes())
                if data:
                    self.overrides = {k: _clean_title(v) for k, v in data.items()
                                      if isinstance(k, str) and isinstance(v, str)}
            except OSError:
                pass

    def resolve(self, raw):
        key = str(raw or '').strip().strip('[]')
        if not key:
            return 'Unknown advancement'
        if key in self.overrides:
            return self.overrides[key] or humanize_advancement(key)
        # Exact translation key emitted by modded Minecraft console output.
        for translation_key in (key, f'{key}.title', f'{key}.name'):
            if self.translations.get(translation_key):
                return self.translations[translation_key]
        if key in self.titles:
            return self.titles[key]
        if key.startswith('advancements.'):
            pieces = key.split('.')
            if len(pieces) >= 3:
                namespace = pieces[1]
                name = '/'.join(pieces[2:])
                for guess in (f'{namespace}:{name}', f'{namespace}:{name.removesuffix(".title")}'):
                    if self.titles.get(guess):
                        return self.titles[guess]
        return humanize_advancement(key)
