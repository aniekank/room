"""English subtitles for Movies and FlyBoy[TV] films.

A film's subtitles come from an .srt (or .vtt) next to it, or failing that from OpenSubtitles, matched to the release
in the file's name so the timing lines up. Either way they're parsed once into cues and kept in data/subs/, so the TV
draws them itself: an old Tizen browser's own subtitle track is not to be relied on.

OpenSubtitles needs a free API key from opensubtitles.com: "opensubtitles_key" in settings.json. Without one,
an .srt dropped next to the film still works.
"""
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import movies
import settings
from paths import DATA

DIR = DATA / 'subs'
API = 'https://api.opensubtitles.com/api/v1'
UA = 'Room v1.0'
HOME = Path.home()


def _file(mid):
    return DIR / (hashlib.sha1(mid.encode()).hexdigest()[:16] + '.json')


def _read(mid):
    try:
        return json.loads(_file(mid).read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _write(mid, d):
    DIR.mkdir(exist_ok=True)
    _file(mid).write_text(json.dumps(d))


def _decode(raw):
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def _secs(t):
    h, m, s = t.replace(',', '.').split(':') if t.count(':') == 2 else ['0'] + t.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse(text):
    """SRT or WebVTT -> [[start, end, text], ...]"""
    cues = []
    for block in re.split(r'\n\s*\n', text.replace('\r', '')):
        m = re.search(r'([\d:]+[,.]\d+)\s*-->\s*([\d:]+[,.]\d+)', block)
        if not m:
            continue
        body = block[m.end():].split('\n', 1)[1] if '\n' in block[m.end():] else ''
        body = re.sub(r'<[^>]+>|\{[^}]*\}', '', body).strip()  # <i>, <font>, {\an8}
        if body:
            cues.append([round(_secs(m.group(1)), 2), round(_secs(m.group(2)), 2), body])
    return cues


def _sidecar(mid):
    """An English subtitle file beside the film, if there is one."""
    p = HOME / mid
    stem = p.stem
    try:
        files = [f for f in p.parent.iterdir() if f.suffix.lower() in ('.srt', '.vtt')]
        files += [f for d in p.parent.iterdir() if d.is_dir() and d.name.lower() in ('subs', 'subtitles')
                  for f in d.iterdir() if f.suffix.lower() in ('.srt', '.vtt')]
    except OSError:
        return None
    english = lambda f: bool(re.search(r'(^|[._ -])(en|eng|english)([._ -]|$)', f.stem.lower()))
    for f in sorted(files, key=lambda f: (not f.stem.startswith(stem), not english(f))):
        if f.stem.startswith(stem) or english(f) or len(files) == 1:
            return f
    return None


def _api(path, body=None):
    key = settings.get('opensubtitles_key')
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={'Api-Key': key, 'User-Agent': UA, 'Accept': 'application/json',
                                          'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _opensubtitles(mid):
    """The English subtitle on OpenSubtitles that best matches this release, as text."""
    m = next((x for x in movies.scan()['movies'] if x['id'] == mid), None)
    name = Path(mid).stem
    title = (m or {}).get('title') or name
    year = re.search(r'\b(19|20)\d\d\b', title + ' ' + name)
    query = re.sub(r'\s*\(\d{4}\)\s*$', '', title)
    q = urllib.parse.urlencode({k: v for k, v in (('query', query), ('year', year.group(0) if year else ''),
                                                    ('languages', 'en'), ('type', 'movie')) if v})
    found = _api(f'/subtitles?{q}').get('data') or []
    words = set(re.findall(r'[a-z0-9]+', name.lower())) - {'the', 'of', 'and', 'a'}

    def score(s):
        a = s['attributes']
        rel = set(re.findall(r'[a-z0-9]+', (a.get('release') or '').lower()))
        return (len(rel & words), a.get('download_count') or 0)
    found = [s for s in found if s['attributes'].get('files') and not s['attributes'].get('foreign_parts_only')]
    if not found:
        return None, ''
    best = max(found, key=score)
    link = _api('/download', {'file_id': best['attributes']['files'][0]['file_id']})['link']
    with urllib.request.urlopen(urllib.request.Request(link, headers={'User-Agent': UA}), timeout=30) as r:
        return _decode(r.read()), f"OpenSubtitles · {best['attributes'].get('release') or query}"


def get(mid):
    """What the TV needs: {cues, on, source} when there are subtitles, {cues: [], can_fetch} when there aren't."""
    d = _read(mid)
    if not d.get('cues'):
        f = _sidecar(mid)
        if f:
            d = {'cues': parse(_decode(f.read_bytes())), 'source': f.name, 'on': d.get('on', False)}
            _write(mid, d)
    return {'cues': d.get('cues', []), 'on': bool(d.get('on')), 'source': d.get('source', ''),
            'can_fetch': bool(settings.get('opensubtitles_key'))}


def toggle(mid, on=None):
    """Subtitles on or off for a film. Turning them on finds them first if there are none yet."""
    d = _read(mid)
    on = (not d.get('on')) if on is None else on
    msg = ''
    if on and not d.get('cues') and not get(mid)['cues']:
        if not settings.get('opensubtitles_key'):
            return dict(get(mid), on=False, msg='No subtitles yet: put an .srt next to the film, or add an opensubtitles_key to settings.json')
        try:
            text, source = _opensubtitles(mid)
        except Exception as e:
            return dict(get(mid), on=False, msg=f'OpenSubtitles did not answer ({str(e)[:60]})')
        if not text:
            return dict(get(mid), on=False, msg='No English subtitles found for this one')
        d = {'cues': parse(text), 'source': source}
        msg = 'English subtitles from ' + source
    d = _read(mid) if not d.get('cues') else d
    d['on'] = on
    _write(mid, d)
    return dict(get(mid), msg=msg or ('Subtitles on' if on else 'Subtitles off'))
