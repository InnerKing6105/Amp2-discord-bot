"""Read-only, bounded discovery of a local AMP 2 Minecraft instance on Windows.

Multiple Minecraft instances are intentionally treated as ambiguous unless a
specific root/hint is provided. No network probes or entire-drive scans.
"""

from pathlib import Path
import os
import re
import string
import sys


def _candidate_datastores(explicit_datastore=None, search_roots=None):
    if explicit_datastore:
        yield Path(explicit_datastore).expanduser()
    if search_roots is not None:
        for root in search_roots:
            yield Path(root)
        return
    if sys.platform == 'win32':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r'SOFTWARE\CubeCoders\AMP\InstanceManager') as key:
                value, _ = winreg.QueryValueEx(key, 'InstanceStore')
                if isinstance(value, str):
                    yield Path(value)
        except (OSError, ImportError):
            pass
        # Check only known AMP datastore names at drive roots (not drives recursively).
        for letter in string.ascii_uppercase:
            if letter in 'AB':
                continue
            yield Path(f'{letter}:\\AMPDatastore')


def _is_minecraft_root(root):
    """Recognize a Minecraft game directory without reading any secret files."""
    return root.is_dir() and (root / 'server.properties').is_file()


def _world_name(root):
    props = root / 'server.properties'
    try:
        for line in props.read_text(encoding='utf-8-sig', errors='replace').splitlines():
            stripped = line.strip()
            if stripped.startswith('#') or '=' not in stripped:
                continue
            key, value = stripped.split('=', 1)
            if key.strip() == 'level-name':
                value = value.strip()
                # World names must be a local directory, not arbitrary traversals.
                if value and value not in {'.', '..'} and '/' not in value and '\\' not in value:
                    return value
    except OSError:
        pass
    return 'world'


def find_minecraft_root(explicit_root='', datastore='', instance_hint='', search_roots=None):
    """Return (root, status). Ambiguous installations are left unresolved."""
    if explicit_root:
        root = Path(explicit_root).expanduser()
        if _is_minecraft_root(root):
            return root, 'explicit'
        return None, 'configured Minecraft root missing server.properties'

    candidates = {}
    for base in _candidate_datastores(datastore, search_roots):
        # Registry can point directly to Instances, or to its parent datastore.
        instances = base if base.name.lower() == 'instances' else base / 'Instances'
        if not instances.is_dir():
            continue
        try:
            folders = sorted((x for x in instances.iterdir() if x.is_dir()), key=lambda x: x.name.lower())
        except OSError:
            continue
        for folder in folders[:150]:
            for root in (folder / 'Minecraft', folder):
                if _is_minecraft_root(root):
                    candidates[str(root).lower()] = root
                    break
    roots = list(candidates.values())
    if not roots:
        return None, 'no AMP Minecraft installation found'
    if len(roots) == 1:
        return roots[0], 'auto'
    hint = re.sub('[^a-z0-9]', '', str(instance_hint).lower())
    if hint:
        matching = [r for r in roots if hint in re.sub('[^a-z0-9]', '', r.parent.name.lower())]
        if len(matching) == 1:
            return matching[0], 'auto (instance match)'
    return None, f'ambiguous: {len(roots)} Minecraft instances found; set MINECRAFT_SERVER_ROOT'


def asset_paths_for_root(root):
    """Cover mod JARs, datapacks, resourcepacks and common pack-loader folders."""
    if root is None or not _is_minecraft_root(Path(root)):
        return []
    root = Path(root)
    candidates = [
        root / 'mods', root / 'resourcepacks', root / 'datapacks',
        root / _world_name(root) / 'datapacks',
        root / 'config' / 'paxi' / 'datapacks',
        root / 'config' / 'paxi' / 'resourcepacks',
        root / 'kubejs' / 'assets', root / 'kubejs' / 'data',
        root / 'global_packs' / 'required_data',
    ]
    seen = set()
    result = []
    for p in candidates:
        key = str(p).lower()
        if p.is_dir() and key not in seen:
            seen.add(key)
            result.append(p)
    return result


def discover_advancement_paths(explicit_paths=(), explicit_root='', datastore='', instance_hint='', search_roots=None):
    """Explicit paths are always kept; safe auto-detection adds missing assets."""
    root, status = find_minecraft_root(explicit_root, datastore, instance_hint, search_roots)
    result = []
    seen = set()
    for raw in [*explicit_paths, *asset_paths_for_root(root)]:
        p = Path(raw).expanduser()
        canonical = str(p).lower()
        if p.exists() and canonical not in seen:
            seen.add(canonical)
            result.append(p)
    return result, status
