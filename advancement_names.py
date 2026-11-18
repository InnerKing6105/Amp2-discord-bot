"""Resolve Minecraft advancement titles from local language and advancement assets.

Offline and read-only: never downloads packs or modifies Minecraft server files.
"""

import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile
from dataclasses import dataclass

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
    """Resolve plain or translated Minecraft text; no external rendering required."""
    if isinstance(value, str):
        return _clean_title(value)
    if isinstance(value, list):
        return _clean_title(''.join(_text_component(part, translations) for part in value))
    if isinstance(value, dict):
        if isinstance(value.get('text'), str):
            base = value['text']
        elif isinstance(value.get('translate'), str):
            key = value['translate']
            base = translations.get(key) or value.get('fallback') or ''
            if not isinstance(base, str):
                base = ''
            args = value.get('with') or []
            if args and isinstance(args, list):
                # Minecraft translations may contain %s / indexed %1$s placeholders.
                def apply(match):
                    index = int(match.group(1)) - 1 if match.group(1) else apply.next_index
                    if not match.group(1):
                        apply.next_index += 1
                    return _text_component(args[index], translations) if 0 <= index < len(args) else ''
                apply.next_index = 0
                base = re.sub(r'%(?:(\d+)\$)?s', apply, base)
        else:
            base = ''
        extra = value.get('extra')
        if isinstance(extra, list):
            base += ''.join(_text_component(part, translations) for part in extra)
        return _clean_title(base)
    return ''


def _details_from_advancement(data, translations):
    display = data.get('display')
    if isinstance(display, dict):
        return (_text_component(display.get('title'), translations),
                _text_component(display.get('description'), translations))
    return '', ''


@dataclass(frozen=True)
class AdvancementDetails:
    title: str
    description: str = ''
    official: bool = False


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
                                   and (q.name.lower() == 'en_us.json' or _ADV_FILE.search(q.as_posix())))))
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
    """Read-only advancement metadata cache, refreshed when the bot restarts."""

    def __init__(self, asset_paths=(), overrides_file=None):
        self.translations = {}
        self.titles = {}
        self.descriptions = {}
        self.overrides = {}
        self.asset_count = 0
        json_assets = []
        for filename, data in _iter_assets(asset_paths):
            obj = _read_json_bytes(data)
            if obj is None:
                continue
            self.asset_count += 1
            if filename.lower().endswith('/en_us.json') or Path(filename).name.lower() == 'en_us.json':
                for k, v in obj.items():
                    if isinstance(k, str) and isinstance(v, str):
                        self.translations[k] = _clean_title(v)
            elif _advancement_id_from_file(filename):
                json_assets.append((filename, obj))
        for filename, obj in json_assets:
            title, desc = _details_from_advancement(obj, self.translations)
            adv_id = _advancement_id_from_file(filename)
            if title:
                self.titles[adv_id] = title
            if desc:
                self.descriptions[adv_id] = desc
        if overrides_file:
            try:
                data = _read_json_bytes(Path(overrides_file).read_bytes())
                if data:
                    self.overrides = {k: _clean_title(v) for k, v in data.items()
                                      if isinstance(k, str) and isinstance(v, str)}
            except OSError:
                pass

    def _id_candidates(self, key):
        result = [key]
        if key.startswith('advancements.'):
            pieces = key.split('.')
            if len(pieces) >= 3:
                namespace = pieces[1]
                path = pieces[2:]
                if path and path[-1] in {'title', 'name', 'description', 'desc'}:
                    path = path[:-1]
                result.append(f'{namespace}:{"/".join(path)}')
                result.append(f'{namespace}:{".".join(path)}')
        if ':' in key:
            namespace, path = key.split(':', 1)
            result.append(f'advancements.{namespace}.{path.replace("/", ".")}')
        return list(dict.fromkeys(result))

    def resolve_info(self, raw):
        key = str(raw or '').strip().strip('[]')
        if not key:
            return AdvancementDetails('Unknown advancement')
        candidates = self._id_candidates(key)
        title = ''
        desc = ''
        official = False
        # Private overrides have highest precedence.
        for cand in candidates:
            if cand in self.overrides and self.overrides[cand]:
                title = self.overrides[cand]
                official = True
                break
        if not title:
            for cand in candidates:
                for translation_key in (cand, f'{cand}.title', f'{cand}.name'):
                    title = self.translations.get(translation_key, '')
                    if title:
                        official = True
                        break
                if title:
                    break
        if not title:
            for cand in candidates:
                title = self.titles.get(cand, '')
                if title:
                    official = True
                    break
        for cand in candidates:
            for desc_key in (f'{cand}.description', f'{cand}.desc'):
                desc = self.translations.get(desc_key, '')
                if desc:
                    break
            if desc:
                break
        if not desc:
            for cand in candidates:
                desc = self.descriptions.get(cand, '')
                if desc:
                    break
        return AdvancementDetails(title or humanize_advancement(key), desc, official)

    def resolve(self, raw):
        return self.resolve_info(raw).title
