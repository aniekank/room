"""Movies: plays video files from a folder (by default iCloud Drive/Movies) on the TV.

The server streams the files with Range requests so the TV's <video> can seek. iCloud may keep
only a placeholder on the Mac (".Name.mp4.icloud" with Optimize Mac Storage on); those are
listed as "in iCloud" and `brctl download` fetches them.
"""
import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import settings
from paths import DATA

ICLOUD = Path.home() / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'
DEFAULT = ICLOUD / 'Movies'
VIDEO = {'.mp4': 'video/mp4', '.m4v': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm',
         '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo', '.ts': 'video/mp2t'}
PLAYS = {'.mp4', '.m4v', '.mov', '.webm'}  # what the Tizen browser's <video> reliably plays
STORE = DATA / 'movies.json'
_lock = threading.Lock()


def folder():
    f = settings.get('movies_folder')
    return Path(f).expanduser() if f else DEFAULT


def label(p):
    """iCloud Drive/Movies instead of ~/Library/Mobile Documents/com~apple~CloudDocs/Movies."""
    p = Path(p)
    try:
        return str(Path('iCloud Drive') / p.relative_to(ICLOUD))
    except ValueError:
        return str(p).replace(str(Path.home()), '~', 1)


def _read():
    try:
        return json.loads(STORE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _title(name):
    stem = Path(name).stem
    return stem.replace('.', ' ').replace('_', ' ').strip() if ' ' not in stem else stem


def scan():
    root = folder()
    if not root.is_dir():
        return {'folder': label(root), 'missing': True, 'movies': []}
    seen = _read()
    out = []
    for p in root.rglob('*'):
        rel = p.relative_to(root)
        if any(part.startswith('.') for part in rel.parts[:-1]):
            continue
        name, cloud = p.name, False
        if name.startswith('.') and name.endswith('.icloud'):  # not downloaded yet
            name, cloud = name[1:-len('.icloud')], True
            rel = rel.with_name(name)
        elif name.startswith('.'):
            continue
        ext = Path(name).suffix.lower()
        if ext not in VIDEO or not (cloud or p.is_file()):
            continue
        key = rel.as_posix()
        mem = seen.get(key, {})
        out.append({'id': key, 'title': _title(name), 'dir': rel.parent.as_posix() if rel.parent.parts else '',
                    'cloud': cloud, 'plays': ext in PLAYS, 'size': 0 if cloud else p.stat().st_size,
                    't': mem.get('t', 0), 'duration': mem.get('duration', 0), 'watched': mem.get('at', '')})
    # Half-watched first, most recent first; then the rest by folder and name.
    started = [m for m in out if 0 < m['t'] < m['duration'] - 120]
    started.sort(key=lambda m: m['watched'], reverse=True)
    rest = [m for m in out if m not in started]
    rest.sort(key=lambda m: (m['dir'].lower(), m['title'].lower()))
    return {'folder': label(root), 'missing': False, 'movies': started + rest}


def path(movie_id):
    """The file for an id, or None. Refuses anything outside the folder."""
    root = folder().resolve()
    p = (root / movie_id).resolve()
    if root not in p.parents or not p.is_file() or p.suffix.lower() not in VIDEO:
        return None
    return p


def fetch(movie_id):
    """Ask iCloud to download a placeholder. Returns right away; the next scan shows it."""
    root = folder()
    rel = Path(movie_id)
    stub = root / rel.parent / f'.{rel.name}.icloud'
    target = stub if stub.exists() else root / rel
    if root.resolve() not in target.resolve().parents:
        return False
    subprocess.Popen(['brctl', 'download', str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def remember(movie_id, t, duration):
    """Where you stopped, so the movie picks up there next time."""
    with _lock:
        seen = _read()
        seen[movie_id] = {'t': int(t), 'duration': int(duration), 'at': datetime.now().isoformat(timespec='seconds')}
        STORE.write_text(json.dumps(seen, indent=1))
