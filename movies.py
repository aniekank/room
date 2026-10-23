"""Movies: plays video files from your folders (by default iCloud Drive/Movies) on the TV.

The server streams the files with Range requests so the TV's <video> can seek. iCloud may keep
only a placeholder on the Mac (".Name.mp4.icloud" with Optimize Mac Storage on); those are
listed as "in iCloud" and `brctl download` fetches them.

A movie's id is its path from your home folder, so positions survive adding or removing folders.
"""
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

import settings
from paths import DATA

HOME = Path.home()
ICLOUD = HOME / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'
DEFAULT = ICLOUD / 'Movies'
VIDEO = {'.mp4': 'video/mp4', '.m4v': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm',
         '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo', '.mpg': 'video/mpeg',  # no .ts: mostly TypeScript
         '.mpeg': 'video/mpeg', '.wmv': 'video/x-ms-wmv'}
PLAYS = {'.mp4', '.m4v', '.mov', '.webm'}  # what the Tizen browser's <video> reliably plays
BUNDLES = ('.app', '.photoslibrary', '.fcpbundle', '.logicx', '.band', '.imovielibrary', '.component', '.vst', '.vst3')
MIN_SIZE = 20_000_000  # smaller local files are samples, trailers and screen clips
STORE = DATA / 'movies.json'
_lock = threading.Lock()
_cache = {'key': None, 'at': 0, 'files': [], 'fetching_until': 0}


def folders():
    """Every folder Movies reads. movies_folders (a list) wins over the older single movies_folder."""
    many = settings.get('movies_folders')
    if many:
        return [Path(f).expanduser() for f in many]
    one = settings.get('movies_folder')
    return [Path(one).expanduser() if one else DEFAULT]


def label(p):
    """iCloud Drive/Movies instead of ~/Library/Mobile Documents/com~apple~CloudDocs/Movies."""
    p = Path(p)
    try:
        return str(Path('iCloud Drive') / p.relative_to(ICLOUD))
    except ValueError:
        return str(p).replace(str(HOME), '~', 1)


def _read():
    try:
        return json.loads(STORE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


JUNK = re.compile(r'\b(360p|480p|576p|720p|1080p|2160p|4k|uhd|hdr|x264|x265|h\.?264|h\.?265|h[. ]?26[45]|hevc|web-?dl|web-?rip|webrip|'
                  r'bluray|blu-ray|brrip|bdrip|dvdrip|hdtv|remastered|extended|proper|repack|complete|aac|ac3|dts|yts)\b',
                  re.I)


YEAR = re.compile(r'\((19|20)\d\d\)$')
EPISODE = re.compile(r'\bS\d\dE\d\d$')
GENERIC = re.compile(r'^(season|series|disc|disk|cd|part|volume|vol|featurettes|extras|specials|bonus)\b', re.I)


def _title(name, parent=''):
    """Oldboy.2003.REMASTERED.1080p.BluRay -> Oldboy (2003); Show.S02E05.WEB -> Show S02E05."""
    stem = Path(name).stem
    stem = re.sub(r'(?<=\w)[._](?=\w)', ' ', stem).replace('_', ' ')  # Mulholland.Drive.2001 -> Mulholland Drive 2001
    stem = re.sub(r'^www\.\S+\s+-\s+', '', stem).strip()
    stem = re.sub(r'^(\[[^\]]*\]\s*-\s*|GetFreeCourses\W?Co\W?Udemy\W|Udemy\s*-\s*)', '', stem, flags=re.I).strip()
    # "I7_____540_2026" or "movie": the folder it sits in usually says what it is.
    if parent and (len(re.sub(r'[^A-Za-z]', '', stem)) < 4 or stem.lower() in ('movie', 'video', 'film')):
        return _title(parent + '.mp4')
    ep = re.search(r'\bS(\d{1,2})\s?E(\d{1,3})\b', stem, re.I)
    if ep:
        show = re.sub(r'[\s\-–\[(]+$', '', stem[:ep.start()])
        return f'{show} S{int(ep.group(1)):02d}E{int(ep.group(2)):02d}'.strip()
    yr = re.search(r'[\s(\[-]((?:19|20)\d\d)[\s)\]-]|[\s(\[-]((?:19|20)\d\d)$', stem)
    if yr and yr.start() > 0:
        return f'{re.sub(r"[\s\-–\[(]+$", "", stem[:yr.start()])} ({yr.group(1) or yr.group(2)})'.replace('  ', ' ')
    junk = JUNK.search(stem)
    if junk and junk.start() > 0:
        stem = stem[:junk.start()]
    stem = re.sub(r'[\s\-–\[(]+$', '', re.sub(r'\[[^\]]*\]', '', stem)).strip()
    return stem or name


def _natural(s):
    """Lesson 2 before lesson 10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]


def _bdecode(b):
    def d(i):
        c = b[i:i + 1]
        if c == b'i':
            j = b.index(b'e', i)
            return int(b[i + 1:j]), j + 1
        if c in (b'l', b'd'):
            i, out = i + 1, ([] if c == b'l' else {})
            while b[i:i + 1] != b'e':
                if c == b'l':
                    v, i = d(i)
                    out.append(v)
                else:
                    k, i = d(i)
                    v, i = d(i)
                    out[k.decode('utf-8', 'replace')] = v
            return out, i + 1
        j = b.index(b':', i)
        n = int(b[i:j])
        return b[j + 1:j + 1 + n], j + 1 + n
    return d(0)[0]


def _unfinished():
    """Paths BiglyBT is still downloading: their files exist at full size but are mostly empty."""
    cfg = HOME / 'Library' / 'Application Support' / 'BiglyBT' / 'downloads.config'
    try:
        mtime = cfg.stat().st_mtime
    except OSError:
        return set()
    if _cache.get('bt_at') == mtime:
        return _cache['bt']
    out = set()
    try:
        for d in _bdecode(cfg.read_bytes()).get('downloads', []):
            try:
                info = _bdecode(Path(d['torrent'].decode()).read_bytes()).get('info', {})
            except (OSError, ValueError, KeyError):
                continue
            total = sum(f['length'] for f in info.get('files', [])) or info.get('length', 0)
            if total and d.get('completedbytes', 0) < total:
                out.add(str(Path(d['save_dir'].decode('utf-8', 'replace')) / info.get('name', b'').decode('utf-8', 'replace')))
    except (OSError, ValueError, KeyError):
        pass
    _cache.update(bt_at=mtime, bt=out)
    return out


def _skip(name, patterns, top=False):
    """A pattern starting with / only matches right inside one of your folders: "/Documents" skips
    iCloud Drive/Documents but not a Documents folder deeper down."""
    if name.startswith('.') or name.endswith(BUNDLES):
        return True
    n = name.lower()
    return any(fnmatch(n, p[1:].lower()) if p.startswith('/') else fnmatch(n, p.lower())
               for p in patterns if top or not p.startswith('/'))


def _is_course(name, courses):
    return any(fnmatch(name.lower(), p.lower()) for p in courses)


def _walk(root, patterns, courses):
    out, partial = [], _unfinished()
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if os.path.join(dp, d) not in partial]
        in_course = any(_is_course(d, courses) for d in Path(dp).relative_to(root).parts)
        # Inside a course you listed, skip patterns don't apply: it's there because you asked for it.
        dns[:] = [d for d in dns if not _skip(d, [] if in_course or _is_course(d, courses) else patterns,
                                                top=Path(dp) == root)]
        for f in fns:
            name, cloud = f, False
            if f.startswith('.') and f.endswith('.icloud'):  # not downloaded yet
                name, cloud = f[1:-len('.icloud')], True
            elif f.startswith('.'):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in VIDEO or _skip(name, [] if in_course else patterns) or os.path.join(dp, name) in partial:
                continue
            p = Path(dp) / f
            size = 0
            if not cloud:
                try:
                    size = p.stat().st_size
                except OSError:
                    continue
                if size < MIN_SIZE:
                    continue
            real = Path(dp) / name
            key = real.relative_to(HOME).as_posix()
            where = label(dp)
            where = '' if where == 'iCloud Drive' else where.removeprefix('iCloud Drive/')
            out.append({'id': key, 'title': _title(name, Path(dp).name if Path(dp) != root else ''), 'dir': where,
                        'cloud': cloud, 'plays': ext in PLAYS, 'size': size})
    return out


def scan():
    roots = folders()
    patterns = settings.get('movies_skip') or []
    names = ', '.join(label(r) for r in roots)
    if not any(r.is_dir() for r in roots):
        return {'folder': names, 'missing': True, 'movies': []}
    courses = settings.get('movies_courses') or []
    key = (tuple(map(str, roots)), tuple(patterns), tuple(courses))
    # A big iCloud Drive takes seconds to walk, so reuse it; look often only while a download is on its way.
    ttl = 3 if time.time() < _cache['fetching_until'] else 60
    with _lock:
        files = _cache['files'] if _cache['key'] == key and time.time() - _cache['at'] < ttl else None
    if files is None:
        files, ids = [], set()
        for r in roots:
            if r.is_dir():
                for m in _walk(r, patterns, courses):
                    if m['id'] not in ids:  # a folder inside another one you also added
                        ids.add(m['id'])
                        files.append(m)
        with _lock:
            _cache.update(key=key, at=time.time(), files=files)
    seen = _read()
    out, have = [], set()
    # The same film twice (two folders, or an MKV and the MP4 made from it): keep one the TV plays, on the Mac if possible.
    for f in sorted(files, key=lambda f: (not f['plays'], f['cloud'])):
        same = f['title'].lower()
        if same in have:
            continue
        have.add(same)
        mem = seen.get(f['id'], {})
        out.append(dict(f, t=mem.get('t', 0), duration=mem.get('duration', 0), watched=mem.get('at', '')))
    # A folder with one video is just that film's folder: those go together under Films.
    per_dir = {}
    for m in out:
        per_dir[m['dir']] = per_dir.get(m['dir'], 0) + 1
    for m in out:
        last = m['dir'].split('/')[-1]
        parts = m['dir'].split('/')
        hit = next((i for i, d in enumerate(parts) if d and _is_course(d, courses)), None)
        if hit is not None:  # a whole course is one group, in lesson order
            m['group'], m['group_name'], m['course'] = '/'.join(parts[:hit + 1]), _title(parts[hit] + '.mp4'), True
            continue
        if per_dir[m['dir']] > 1 and m['dir']:  # a series or a collection: its own group
            name = _title(last + '.mp4')
            parts = m['dir'].split('/')
            if GENERIC.match(last) and len(parts) > 1:  # "Season 1" alone doesn't say which show
                name = f"{_title(parts[-2] + '.mp4')} · {name}"
            m['group'], m['group_name'] = m['dir'], name
            continue
        if not YEAR.search(m['title']) and last:
            named = _title(last + '.mp4')  # the year is often only on the folder
            if YEAR.search(named):
                m['title'] = named
        m['group'] = m['group_name'] = ('Films' if YEAR.search(m['title']) else
                                        'Single episodes' if EPISODE.search(m['title']) else 'Other videos')
    # Half-watched first, most recent first; then Films by title, then each series or collection.
    started = [m for m in out if 0 < m['t'] < m['duration'] - 120]
    started.sort(key=lambda m: m['watched'], reverse=True)
    rest = [m for m in out if m not in started]
    order = {'Films': 0, 'Single episodes': 3, 'Other videos': 4}
    rest.sort(key=lambda m: (2 if m.get('course') else order.get(m['group'], 1), m['group_name'].lower(),
                             _natural(m['id']) if m.get('course') else _natural(m['title'])))
    return {'folder': names, 'missing': False, 'movies': started + rest}


def _inside(p):
    p = p.resolve()
    return any(r.resolve() in p.parents for r in folders())


def path(movie_id):
    """The file for an id, or None. Refuses anything outside your movie folders."""
    p = HOME / movie_id
    if not _inside(p) or not p.is_file() or p.suffix.lower() not in VIDEO:
        return None
    return p.resolve()


def fetch(movie_id):
    """Ask iCloud to download a placeholder. Returns right away; the next scan shows it."""
    p = HOME / movie_id
    stub = p.parent / f'.{p.name}.icloud'
    target = stub if stub.exists() else p
    if not _inside(target):
        return False
    subprocess.Popen(['brctl', 'download', str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with _lock:
        _cache['fetching_until'] = time.time() + 1800  # so the TV sees it arrive
    return True


def remember(movie_id, t, duration):
    """Where you stopped, so the movie picks up there next time."""
    with _lock:
        seen = _read()
        seen[movie_id] = {'t': int(t), 'duration': int(duration), 'at': datetime.now().isoformat(timespec='seconds')}
        STORE.write_text(json.dumps(seen, indent=1))
