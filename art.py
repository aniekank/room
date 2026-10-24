"""Official artwork for your films and shows: the poster from the title's Wikipedia article (films), or the show's
title card. Looked up once in the background, one title every few seconds (Wikipedia asks clients to go easy),
resized for the TV and kept in data/posters.
"""
import json
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import settings
from paths import DATA

POSTERS = DATA / 'posters'
INDEX = POSTERS / 'index.json'  # key -> file name, or '' for "looked, found nothing" (tried again after a week)
UA = {'User-Agent': 'Room/1.0 (personal TV channels; https://github.com/aniekank/room)'}
_lock = threading.Lock()
_state = {'started': False, 'until': 0}


def key(title, kind):
    return f'{kind}:{re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()}'


def _index():
    try:
        return json.loads(INDEX.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def poster(title, kind):
    """The poster's file name for a film ('film') or show ('show'), or '' if there isn't one yet."""
    v = _index().get(key(title, kind))
    return v['file'] if isinstance(v, dict) and v.get('file') and (POSTERS / v['file']).is_file() else ''


def for_movie(m):
    """The poster URL for an entry from movies.scan(): a film's own, or its show's."""
    import station
    if m.get('course'):
        return ''
    f = poster(m['title'], 'film') if m['group'] == 'Films' else poster(station.show_of(m), 'show')
    return f'/poster/{f}' if f else ''


def path(name):
    p = POSTERS / Path(name).name
    return p if name and p.is_file() and p.suffix == '.jpg' else None


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def _find(title, kind):
    """The article's lead image: a film's poster, a show's title card."""
    m = re.match(r'^(.*?)\s*\((\d{4})\)$', title)
    name, year = (m.group(1), m.group(2)) if m else (title, '')
    over = settings.get('poster_articles') or {}
    if name in over or title in over:  # you named the article (two shows share a name), or said there's no poster
        article = over.get(name, over.get(title))
        if not article:
            return ''
        d = json.loads(_get('https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode({
            'action': 'query', 'format': 'json', 'titles': article, 'prop': 'pageimages', 'piprop': 'original', 'pilicense': 'any'})))
        return next(((p.get('original') or {}).get('source', '') for p in d['query']['pages'].values()), '')
    norm = lambda t: re.sub(r'[^a-z0-9]', '', t.lower().replace('&', 'and'))
    want = norm(name)
    for exact, q in ((False, f'{name} {year} film' if kind == 'film' else f'{name} TV series'), (True, name)):
        d = json.loads(_get('https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode({
            'action': 'query', 'format': 'json', 'generator': 'search', 'gsrsearch': q, 'gsrlimit': 5,
            'prop': 'pageimages', 'piprop': 'original', 'pilicense': 'any'})))
        for p in sorted((d.get('query') or {}).get('pages', {}).values(), key=lambda p: p.get('index', 9)):
            src = (p.get('original') or {}).get('source', '')
            title = norm(p['title'])
            # the bare-title search only counts an article named exactly that ("88" alone found an Oldsmobile)
            ok = title == want if exact else want[:10] in title
            if src and ok and not src.split('?')[0].lower().endswith('.svg'):  # a logo graphic isn't a poster
                return src
        time.sleep(2)
    return ''


def _fetch(title, kind):
    url = _find(title, kind)
    if not url:
        return ''
    POSTERS.mkdir(parents=True, exist_ok=True)
    k = key(title, kind)
    name = re.sub(r'[^a-z0-9]+', '-', k.split(':', 1)[1])[:60] + '.jpg'
    raw = POSTERS / ('.dl' + Path(urllib.parse.urlparse(url).path).suffix.lower())
    raw.write_bytes(_get(url))
    # one size for the TV: 600 tall is plenty on a 768-line panel, and keeps each one well under 100 KB
    subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '80', '--resampleHeight', '600', str(raw),
                    '--out', str(POSTERS / name)], capture_output=True)
    raw.unlink(missing_ok=True)
    return name if (POSTERS / name).is_file() else ''


def _wanted():
    import movies
    import station
    every = movies.scan()['movies']  # films still waiting to be converted get their posters too
    films = [(m['title'], 'film') for m in every if m['group'] == 'Films']
    shows = [(name, 'show') for name in station._shows_of([m for m in every if m['plays']], 'series')]
    return shows + films


def _worker(log):
    while True:
        try:
            idx, done = _index(), 0
            for title, kind in _wanted():
                v = idx.get(key(title, kind))
                if isinstance(v, dict) and (v.get('file') or time.time() - v.get('at', 0) < 7 * 86400):
                    continue
                while time.time() < _state['until']:
                    time.sleep(30)
                try:
                    name = _fetch(title, kind)
                except urllib.error.HTTPError as e:
                    if e.code == 429:  # Wikipedia asked us to slow down
                        _state['until'] = time.time() + 900
                        continue
                    name = ''
                except Exception:
                    name = ''
                with _lock:
                    idx = _index()
                    idx[key(title, kind)] = {'file': name, 'at': time.time()}
                    INDEX.write_text(json.dumps(idx, indent=1))
                done += bool(name)
                time.sleep(4)
            if done:
                log(f'art: {done} posters found')
        except Exception as e:
            log(f'art: {e}')
        time.sleep(3600)


def start(log=print):
    if not _state['started']:
        _state['started'] = True
        threading.Thread(target=_worker, args=(log,), daemon=True).start()
