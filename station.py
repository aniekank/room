"""FlyBoy[TV]: your own always-on channel. Tune in and it's mid-show, like real TV.

The server keeps the playout: what's on, when it started, and a short queue of what's next. The day runs
in dayparts (Your Day in the morning, series through the day, FlyBoy Academy after lunch, a film in prime
time, the FlyBoyRadio Vault late at night) with a FlyBoy[TV] ident between programs.

The TV can only play what's on the Mac, so programs coming up from iCloud are downloaded ahead and dropped
again after they air. One that isn't down in time is bumped for a segment and tried in the next slot.

Brand assets and data live in a kit folder in iCloud Drive (FlyBoy[TV]/), so the background server never
needs the Desktop; `room station sync` refreshes it from ~/Desktop/FlyBoyRadio.
"""
import json
import plistlib
import random
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import movies
import settings
import sources
from paths import DATA

HOME = Path.home()
KIT_DEFAULT = movies.ICLOUD / 'FlyBoy[TV]'
SOURCE_DEFAULT = HOME / 'Desktop' / 'FlyBoyRadio'
STATE = DATA / 'station.json'
_lock = threading.Lock()

DAYPARTS = [  # (from hour, name, what airs, weighted)
    (2, 'Overnight', {'tapes': 4, 'vault': 2, 'crates': 2}),
    (6, 'Morning', {'yourday': 2, 'series': 5, 'crates': 1, 'tapes': 1}),
    (10, 'Daytime', {'series': 5, 'crates': 2, 'vault': 1, 'tapes': 1}),
    (13, 'FlyBoy Academy', {'course': 5, 'crates': 1, 'tapes': 1}),
    (16, 'Afternoon', {'series': 5, 'vault': 1, 'promo': 1, 'queenpin': 1}),
    (19, 'Prime Time', {'queenpin': 1, 'film': 5, 'series': 1, 'promo': 1}),
    (23, 'Late Night', {'tapes': 2, 'vault': 3, 'recording': 1, 'film': 2, 'queenpin': 1}),
]
LEAD = {'yourday', 'queenpin'}  # what opens a daypart before anything else: Your Day at 6am, Queenpin at 4pm, 7pm and 11pm
SEG_LEN = {'ident': 7, 'yourday': 80, 'vault': 6 * 100, 'crates': 3 * 75, 'tapes': 3 * 90, 'queenpin': 75}
BEATS_DEFAULT = movies.ICLOUD / 'TASK Beats Backup 2026-10-03' / 'Desktop'
BEAT_DIRS = ('Recovered beats*', 'Demo cuts*', 'California Dreamin*')  # plus the finished tracks at the top
BEAT_SKIP = ('*before-after*', '*spot*', '*EXPLICIT*', '*T.A.S.K. tag*', 'she-chose-clean*', 'She Chose - 3%*')
QUEENPIN = {'lotti-gold': 'Lotti Gold', 'mei-li': 'Mei Li', 'sable': 'Sable · The Architect', 'babi-blu': 'Babi Blu',
            'champagne': 'Champagne', 'dynasty': 'Dynasty', 'goldie': 'Goldie Knox', 'block_party': 'Butta',
            'city_spotlight': 'Babi Blu'}


def kit():
    k = settings.get('station_kit')
    return Path(k).expanduser() if k else KIT_DEFAULT


def daypart(t):
    h = datetime.fromtimestamp(t).hour
    cur = DAYPARTS[-1]
    for d in DAYPARTS:
        if (h - d[0]) % 24 < (h - cur[0]) % 24:
            cur = d
    return cur


# ---------------------------------------------------------------- the kit

def sync(log=print):
    """Copy the FlyBoyRadio assets into the kit in iCloud Drive (run from Terminal: the Desktop is off-limits
    to background apps). Small files only; the archive recording stays where it is and airs from there."""
    src, dst = Path(settings.get('station_source') or SOURCE_DEFAULT).expanduser(), kit()
    picks = [('Flyboy Radio - Every Playlist (2008-2011).md', 'data/playlists.md'),
             ('Crate Index/data.json', 'data/crates.json'),
             ('Digging HQ.md', 'data/digging.md')]
    picks += [(f'FlyBoyRadio Instagram/{p.name}', f'art/{p.name}') for p in sorted((src / 'FlyBoyRadio Instagram').glob('flyboyradio-*.png'))]
    picks += [(f'FlyBoyRadio media/{p.name}', 'art/flyer.jpg') for p in (src / 'FlyBoyRadio media').glob('*flyer*.jpg')]
    picks += [(f'FlyBoyRadio media/promo/{p.name}', f'promos/{p.name}') for p in (src / 'FlyBoyRadio media' / 'promo').glob('*-16x9.mp4')]
    tag = HOME / 'Desktop' / 'Beats & Music' / 'Original T.A.S.K. tag (candidate, 0.4-6.4s of the FlyBoyRadio intro).wav'
    n = 0
    for rel, out in picks:
        a, b = src / rel, dst / out
        if a.exists() and (not b.exists() or b.stat().st_mtime < a.stat().st_mtime):
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(a, b)
            n += 1
    if tag.exists() and not (dst / 'audio/tag.wav').exists():
        (dst / 'audio').mkdir(parents=True, exist_ok=True)
        shutil.copy2(tag, dst / 'audio/tag.wav')
        n += 1
    n += _sync_art(dst)
    log(f'kit: {n} files updated in {movies.label(dst)}')
    return n


MOTION = HOME / 'Desktop' / 'Motion'
ART = {  # kit folder: [(source, name in the kit)]; the Passenger Princess Mode shots are the night versions
    'drive': [(MOTION / 'Daytime - GPT kit' / f, f.split(' - ')[-1]) for f in
              ('01 tesla - task-driving.png', '02 tesla - task-autopilot.png', '14 bmw - task-driving-89.png',
               '01 tesla - task-driving-day.png', '14 bmw - task-driving-89-day.png')] +
             [(MOTION / f, f) for f in ('alpine.png', 'rollin-cover-no-text.png')],
    'tapes': [(HOME / 'Desktop' / 'Marketing & Social' / 'Instagram Carousels' / '1 The Tapes' / f'tapes-0{i}.png', f'tapes-0{i}.png') for i in range(1, 9)],
    'queenpin': [(MOTION / 'Daytime - GPT kit' / f, f.split(' - ')[-1]) for f in
                 ('06 tesla - lotti-gold.png', '07 tesla - lotti-gold-look.png', '08 tesla - mei-li.png', '09 tesla - mei-li-look.png',
                  '10 tesla - sable.png', '11 tesla - sable-look.png', '12 tesla - babi-blu.png', '13 tesla - babi-blu-look.png',
                  '16 bmw - champagne-89.png', '17 bmw - champagne-89-look.png', '18 bmw - dynasty-89.png', '19 bmw - dynasty-89-look.png')] +
                [(MOTION / 'Queenpin - Passenger Princess Mode - GPT kit' / f, f) for f in
                 ('01 Lotti Gold - reference.png', '02 Mei Li - reference.png', '03 Sable (The Architect) - reference 2, with her card.png',
                  '04 Babi Blu - reference.png', '05 Dynasty - reference.png', '06 Champagne - reference.png')] +
                [(HOME / 'Desktop' / 'Screenshots & Images' / 'queenpin-linkedin-square.png', 'era-one-build-log.png')] +
                [(movies.ICLOUD / 'Mac Offload' / 'Downloads' / 'Queenpin_Visuals_From_This_Chat' / f, f) for f in
                 ('goldie_knox_queenpin_of_wealth.png', 'queenpin_of_the_block_party.png',
                  'queenpin_rise_of_the_crown_fight_night.png', 'queenpin_in_the_city_spotlight.png')],
}


def _sync_art(dst):
    """Copies the drive, tapes and Queenpin art into the kit as JPEGs sized for the TV (sips ships with macOS)."""
    n = 0
    for folder, items in ART.items():
        for a, name in items:
            b = dst / 'art' / folder / (Path(name).stem + '.jpg')
            stub = a.parent / f'.{a.name}.icloud'
            if not a.exists() and stub.exists():  # still in iCloud: bring it down first
                subprocess.run(['brctl', 'download', str(a)], capture_output=True)
                for _ in range(120):
                    if a.exists():
                        break
                    time.sleep(0.5)
            if not a.exists() or (b.exists() and b.stat().st_mtime >= a.stat().st_mtime):
                continue
            b.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '82', '-Z', '1400', str(a), '--out', str(b)],
                           capture_output=True)
            n += b.exists()
    return n


def kit_path(rel):
    """A file inside the kit, or None. Downloads it from iCloud first if needed (they're small)."""
    root = kit().resolve()
    p = (root / rel).resolve()
    if root not in p.parents:
        return None
    if not p.exists() and (p.parent / f'.{p.name}.icloud').exists():
        subprocess.run(['brctl', 'download', str(p)], capture_output=True, timeout=10)
        for _ in range(60):
            if p.exists():
                break
            time.sleep(0.5)
    return p if p.is_file() else None


def kit_files(sub, pattern='*'):
    d = kit() / sub
    if not d.is_dir():
        return []
    names = {p.name for p in d.glob(pattern) if not p.name.startswith('.')}
    names |= {p.name[1:-7] for p in d.glob('.*.icloud')}
    return sorted(f'{sub}/{n}' for n in names if Path(n).match(pattern))


# ---------------------------------------------------------------- your beats

def beats_root():
    b = settings.get('station_beats')
    return Path(b).expanduser() if b else BEATS_DEFAULT


_beats = None


def beats():
    """Every beat worth airing: the recovered 2009-2011 beats, demo cuts and the finished tracks."""
    global _beats
    if _beats is not None:
        return _beats
    from fnmatch import fnmatch
    root, out = beats_root(), []
    if not root.is_dir():
        return []
    for p in root.rglob('*'):
        name = p.name[1:-7] if p.name.startswith('.') and p.name.endswith('.icloud') else p.name
        if Path(name).suffix.lower() not in ('.mp3', '.m4a', '.wav') or name.startswith('.'):
            continue
        rel = p.parent.relative_to(root) / name
        top = rel.parts[0] if len(rel.parts) > 1 else ''
        if len(rel.parts) > 2 or (top and not any(fnmatch(top, d) for d in BEAT_DIRS)) or any(fnmatch(name, x) for x in BEAT_SKIP):
            continue
        title = re.sub(r'\s*-\s*\d% faster.*$|\s*\((clean|brightened)\)|-cut$|_Master$|\s*-\s*demo edit.*$', '', Path(name).stem, flags=re.I)
        era = '2009-2011' if '2009' in top else 'Demo cut' if top.startswith('Demo') else 'TASK[productions]'
        out.append({'f': rel.as_posix(), 'title': title.replace('_', ' ').strip(), 'era': era})
    _beats = out
    return out


BEAT_CACHE = DATA / 'beats'  # on the Mac for good: iCloud can take minutes to hand over a 5 MB file when it's busy


def beat_path(rel, wait=0):
    """A beat on the Mac: from the cache, or copied into it from iCloud Drive. Asks iCloud for it when it isn't down yet,
    waiting up to `wait` seconds (the TV never waits; the background warm-up does)."""
    root = beats_root().resolve()
    p = (root / rel).resolve()
    if root not in p.parents:
        return None
    cached = BEAT_CACHE / rel
    if cached.is_file():
        return cached
    if not p.exists() and (p.parent / f'.{p.name}.icloud').exists():
        subprocess.run(['brctl', 'download', str(p)], capture_output=True, timeout=10)
        end = time.time() + wait
        while not p.exists() and time.time() < end:
            time.sleep(1)
    if not p.is_file():
        return None
    cached.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, cached)
    return cached


def on_mac(b):
    return (BEAT_CACHE / b['f']).is_file() or (beats_root() / b['f']).is_file()


def some_beats(rng, n):
    """Beats for a segment, from the ones already on the Mac when there are enough."""
    ready = [b for b in beats() if on_mac(b)]
    pool = ready if len(ready) >= n else beats()
    return rng.sample(pool, min(n, len(pool))) if pool else []


def warm_beats(log=print):
    """In the background: bring every beat down once, a few minutes apart so the converter and the station still get iCloud."""
    def go():
        for b in beats():
            if shutil.disk_usage(HOME).free < 4e9:
                return
            if not (BEAT_CACHE / b['f']).is_file() and beat_path(b['f'], wait=600):
                time.sleep(5)
        log(f'station: {sum(on_mac(b) for b in beats())} of {len(beats())} beats on the Mac')
    threading.Thread(target=go, daemon=True).start()


def art(folder):
    return kit_files(f'art/{folder}', '*.jpg')


# ---------------------------------------------------------------- FlyBoyRadio Vault

_shows = None


def shows():
    """Every logged show from the playlists file: date, link and tracks."""
    global _shows
    if _shows is not None:
        return _shows
    p = kit_path('data/playlists.md')
    out, cur = [], None
    for line in (p.read_text().splitlines() if p else []):
        m = re.match(r'^### (\w{3}) (\d{1,2}) (\w{3}) (\d{4})', line)
        if m:
            cur = {'date': datetime.strptime(' '.join(m.groups()[1:]), '%d %b %Y').date().isoformat(),
                   'label': line[4:].strip(), 'tracks': []}
            out.append(cur)
            continue
        t = re.match(r'^\d+\.\s+(.+?):\s+(.+?)(?:\s{2}_\((.*)\)_)?\s*$', line)
        if cur and t:
            artist, title, note = t.group(1).strip(), t.group(2).strip(), (t.group(3) or '').strip()
            own = 'T.A.S.K' in (artist + title + note)
            cur['tracks'].append({'artist': artist, 'title': title, 'note': note, 'own': own})
    _shows = [s for s in out if s['tracks']]
    return _shows


def pick_show(rng):
    """Nearest anniversary first: a show from this week of the year if there is one."""
    all_ = shows()
    if not all_:
        return None
    today = datetime.now().timetuple().tm_yday

    def gap(s):
        d = (datetime.fromisoformat(s['date']).timetuple().tm_yday - today) % 365
        return min(d, 365 - d)
    near = [s for s in all_ if gap(s) <= 7]
    return rng.choice(near or all_)


# ---------------------------------------------------------------- From the Crates

_crates = None


def crates():
    global _crates
    if _crates is None:
        p = kit_path('data/crates.json')
        try:
            recs = json.loads(p.read_text())['records'] if p else []
        except (ValueError, KeyError):
            recs = []
        _crates = [r for r in recs if r.get('img') and r.get('artist') and r.get('title')]
    return _crates


# ---------------------------------------------------------------- YouTube for segments

def _yt(query):
    def build():
        hits = [e for e in sources._yt_search(query, 5) if not e['live'] and 60 <= (e['duration'] or 0) <= 1500]
        return hits[0]['id'] if hits else ''
    try:
        return sources.cached('yt:' + query.lower(), 30 * 86400, build)
    except Exception:
        return ''


def resolve(item):
    """Find YouTube ids for a segment's tracks or records. Runs in the background ahead of airtime."""
    for t in item.get('tracks') or item.get('records') or []:
        if not t.get('vid'):
            t['vid'] = _yt(f"{t['artist']} {t['title']}")


# ---------------------------------------------------------------- library picks

def _cloud_size(m):
    stub = HOME / Path(m['id']).parent / f".{Path(m['id']).name}.icloud"
    try:
        return plistlib.loads(stub.read_bytes()).get('NSURLFileSizeKey', 0)
    except (OSError, ValueError):
        return 0


def _estimate(m):
    if m.get('duration'):
        return m['duration']
    size = m.get('size') or _cloud_size(m)
    name = (m['title'] + ' ' + m['dir']).lower()
    rate = 15e6 if '2160p' in name else 5e6 if '1080p' in name else 2.5e6 if '720p' in name else 1.5e6
    return int(min(4 * 3600, max(600, size * 8 / rate))) if size else 45 * 60


def _ready(m_id):
    return (HOME / m_id).is_file()


def _video(m, st):
    return {'kind': 'video', 'id': m['id'], 'title': m['title'], 'show': 'Film' if m['group'] == 'Films' else show_of(m),
            'dur': _estimate(m), 'cloud': not _ready(m['id'])}


EPISODE = re.compile(r'\bS\d\dE\d\d\b|\bEp\.? ?\d', re.I)


def show_of(m):
    """The Cosby Show S03 and New York Undercover · Season 2 belong to one show each."""
    if m.get('course'):
        return m['group_name']
    return re.sub(r'\s*(·\s*)?(Season\s*\d+|S\d\d)\b.*$', '', m['group_name'], flags=re.I).strip() or m['group_name']


def _shows_of(lib, kind):
    by = {}
    for m in lib:
        if kind == 'course' and m.get('course'):
            by.setdefault(show_of(m), []).append(m)
        elif kind == 'series' and not m.get('course') and m['group'] not in ('Films', 'Other videos', 'Single episodes'):
            by.setdefault(show_of(m), []).append(m)
    if kind == 'series':  # a series has numbered episodes; a folder of clips doesn't
        by = {k: v for k, v in by.items() if len(v) >= 3 and sum(bool(EPISODE.search(x['title'])) for x in v) * 2 >= len(v)}
    return {k: sorted(v, key=lambda m: movies._natural(m['id'])) for k, v in by.items()}


def pick(kind, st, rng):
    lib = [m for m in movies.scan()['movies'] if m['plays']]
    aired = st.setdefault('aired', {})
    if kind in ('series', 'course'):
        by = _shows_of(lib, kind)
        if not by:
            return None
        names = sorted(by)
        rot = st.setdefault('rotation', {})
        g = names[rot.get(kind, 0) % len(names)]
        rot[kind] = rot.get(kind, 0) + 1
        eps = by[g]
        nxt = st.setdefault('next_ep', {})
        i = nxt.get(g, 0) % len(eps)
        nxt[g] = i + 1
        return _video(eps[i], st)
    if kind == 'film':
        films = [m for m in lib if m['group'] == 'Films']
        fresh = [m for m in films if time.time() - aired.get(m['id'], 0) > 30 * 86400] or films
        if not fresh:
            return None
        ready = [m for m in fresh if _ready(m['id'])]
        m = rng.choice(ready if ready and rng.random() < 0.5 else fresh)  # half the time, whatever's on the Mac
        aired[m['id']] = time.time()  # booked: don't book it again this month
        return _video(m, st)
    if kind == 'promo':
        p = kit_files('promos', '*.mp4')
        return {'kind': 'promo', 'src': rng.choice(p), 'title': 'FlyBoy[TV] presents', 'dur': 60} if p else None
    if kind == 'recording':
        rec = settings.get('station_recording')
        return {'kind': 'recording', 'path': rec, 'title': 'FlyBoyRadio, live on WMUC', 'dur': 3 * 3600,
                'show': _show_for_recording(rec)} if rec else None
    if kind == 'vault':
        s = pick_show(rng)
        if not s:
            return None
        tracks = [dict(t) for t in s['tracks'] if not t['own']]
        if not tracks:
            return None
        rng.shuffle(tracks)
        return {'kind': 'vault', 'title': f"FlyBoyRadio Vault · {s['label']}", 'date': s['date'], 'label': s['label'],
                'all': [f"{t['artist']}: {t['title']}" for t in s['tracks']][:24], 'tracks': tracks[:6], 'per': 100,
                'dur': 100 * min(6, len(tracks))}
    if kind == 'crates':
        recs = crates()
        if not recs:
            return None
        picks = rng.sample(recs, min(3, len(recs)))
        return {'kind': 'crates', 'title': 'From the Crates', 'records': [dict(r) for r in picks], 'per': 75, 'dur': 75 * len(picks)}
    if kind == 'yourday':  # one of your beats underneath
        return {'kind': 'yourday', 'title': 'Your Day', 'dur': SEG_LEN['yourday'], 'beats': some_beats(rng, 1)}
    if kind == 'tapes':
        if not beats():
            return None
        picks = some_beats(rng, 3)
        slides = art('drive') + art('tapes')
        rng.shuffle(slides)
        return {'kind': 'tapes', 'title': 'Ride With Me · The Tapes', 'show': 'TASK[productions]', 'beats': picks, 'per': 90,
                'dur': 90 * len(picks), 'slides': slides}
    if kind == 'queenpin':
        imgs = art('queenpin')
        if not imgs:
            return None
        named = lambda i: next((v for k, v in QUEENPIN.items() if k in i.lower().replace(' ', '-')), '')
        by = {}
        for i in imgs:
            if 'build-log' not in i:
                by.setdefault(named(i), []).append(i)
        for v in by.values():
            rng.shuffle(v)
        names = list(by)
        rng.shuffle(names)
        order = [i for i in imgs if 'build-log' in i]  # opens on the Era One build log
        while len(order) < 15 and any(by.values()):  # round the cast: nobody twice in a row
            for n in names:
                if by[n]:
                    order.append(by[n].pop())
        slides = [{'img': i, 'name': named(i)} for i in order[:15]]
        return {'kind': 'queenpin', 'title': 'Queenpin: Era One', 'show': 'TASK Enterprises', 'dur': SEG_LEN['queenpin'],
                'slides': slides, 'beats': some_beats(rng, 1)}
    return None


def _show_for_recording(path):
    m = re.search(r'(\d{4})(\d{2})(\d{2})', path or '')
    if not m:
        return None
    d = datetime(*map(int, m.groups())).date()
    best = min(shows(), key=lambda s: abs((datetime.fromisoformat(s['date']).date() - d).days), default=None)
    return best and {'label': best['label'], 'all': [f"{t['artist']}: {t['title']}" for t in best['tracks']][:30]}


# ---------------------------------------------------------------- playout

def _load():
    try:
        return json.loads(STATE.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _save(st):
    STATE.write_text(json.dumps(st, indent=1))


def _stamp(item, start):
    item.setdefault('uid', uuid.uuid4().hex[:10])
    item['start'] = start
    return item


def _plan(st, at):
    """The next block: an ident, then a program for the daypart it starts in."""
    rng = random.Random()
    start, name, weights = daypart(at)
    block = []
    if st.get('daypart') != name:  # a new daypart opens with its lead segment
        st['daypart'] = name
        for k in weights:
            if k in LEAD:
                block.append(pick(k, st, rng))
    kinds = [k for k in weights if k not in LEAD or len(weights) == 1]
    last = st.get('last_kind')
    for _ in range(6):
        k = rng.choices(kinds, [weights[x] for x in kinds])[0]
        if k == last and len(kinds) > 1:
            continue
        prog = pick(k, st, rng)
        if prog:
            st['last_kind'] = k
            block.append(prog)
            break
    out = [{'kind': 'ident', 'title': 'FlyBoy[TV]', 'dur': SEG_LEN['ident']}]
    return out + [b for b in block if b]


def _fill(st, now):
    q = st.setdefault('queue', [])
    t = (st['current']['start'] + st['current']['dur']) if st.get('current') else now
    for it in q:
        t += it['dur']
    while len(q) < 5:
        for it in _plan(st, t):
            it.setdefault('uid', uuid.uuid4().hex[:10])
            q.append(it)
            t += it['dur']


def _air(st, item):
    if item['kind'] == 'video':
        st.setdefault('aired', {})[item['id']] = time.time()


def _finished(item):
    """After airing: give back the space for anything the station downloaded."""
    if item.get('kind') == 'video' and item.get('fetched'):
        subprocess.Popen(['brctl', 'evict', str(HOME / item['id'])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _advance(st, now):
    if st.get('current'):
        _finished(st['current'])
    start = (st['current']['start'] + st['current']['dur']) if st.get('current') else now
    q = st['queue']
    nxt = q.pop(0)
    if nxt['kind'] in ('video', 'recording') and not _item_ready(nxt):
        nxt['bumped'] = nxt.get('bumped', 0) + 1
        if nxt['bumped'] <= 4:
            q.insert(0, nxt)  # try again right after the filler
        nxt = pick('crates', st, random.Random()) or {'kind': 'ident', 'title': 'FlyBoy[TV]', 'dur': 7}  # short, while it downloads
    st['current'] = _stamp(nxt, start)
    _air(st, nxt)


def _item_ready(item):
    if item['kind'] == 'video':
        return _ready(item['id'])
    if item['kind'] == 'recording':
        return Path(item['path']).expanduser().is_file()
    return True


def now():
    """What's on right now, how far in, and what's next. Advances the playout as wall-clock time passes."""
    t = time.time()
    with _lock:
        st = _load()
        cur = st.get('current')
        if not cur or t - (cur['start'] + cur['dur']) > 1800:  # first run, or the Mac slept: start fresh, no catch-up
            st['queue'], st['current'], st['daypart'] = [], None, None
            _fill(st, t)
            _advance(st, t)
            st['current']['start'] = t
        while t >= st['current']['start'] + st['current']['dur']:
            _fill(st, t)
            _advance(st, t)
        _fill(st, t)
        _save(st)
        cur, q = st['current'], st['queue']
    _prepare(cur, q)
    nexts, s = [], cur['start'] + cur['dur']
    for it in q:
        nexts.append({'title': it['title'], 'show': it.get('show', ''), 'kind': it['kind'], 'start': s})
        s += it['dur']
    return {'now': t, 'item': cur, 'offset': t - cur['start'], 'next': nexts,
            'daypart': daypart(t)[1], 'ends': cur['start'] + cur['dur']}


def actual_duration(uid, dur):
    """The TV knows a video's real length once it loads; correct the schedule with it."""
    with _lock:
        st = _load()
        cur = st.get('current') or {}
        if cur.get('uid') == uid and dur and abs(cur['dur'] - dur) > 2:
            cur['dur'] = int(dur)
            if cur.get('kind') == 'video':
                m = movies._read().get(cur['id'], {})
                movies.remember(cur['id'], m.get('t', 0), dur)
            _save(st)


def skip():
    """From the remote: end the current program now."""
    with _lock:
        st = _load()
        if st.get('current'):
            st['current']['dur'] = max(1, int(time.time() - st['current']['start']))
            _save(st)
    return now()


ON_DEMAND = ('queenpin', 'tapes', 'vault', 'crates', 'yourday')


def play_now(kind):
    """From the remote: cut to a segment now. What was on ends here; the schedule carries on after it."""
    if kind not in ON_DEMAND:
        return None
    item = pick(kind, _load(), random.Random())
    if not item:
        return None
    with _lock:
        st = _load()
        if st.get('current'):
            _finished(st['current'])
        item['uid'] = uuid.uuid4().hex[:10]
        st['current'] = _stamp(item, time.time())
        _save(st)
    _prepare(item, [])
    return now()


_busy = set()


def _prepare(cur, q):
    """In the background: download what's coming up from iCloud and look up YouTube ids for segments."""
    for it in [cur] + q[:3]:
        key = it.get('uid') or id(it)
        if key in _busy:
            continue
        if it.get('beats') and not it.get('beats_ready'):  # bring the beats down from iCloud ahead of airtime
            _busy.add(key)
            threading.Thread(target=_fetch_beats, args=(it,), daemon=True).start()
            continue
        if it['kind'] in ('vault', 'crates') and any(not t.get('vid') for t in it.get('tracks') or it.get('records') or []):
            _busy.add(key)
            threading.Thread(target=_resolve_saved, args=(it,), daemon=True).start()
        elif it['kind'] in ('video', 'recording') and not _item_ready(it) and not it.get('fetched'):
            path = HOME / it['id'] if it['kind'] == 'video' else Path(it['path']).expanduser()
            try:
                need = (_cloud_size({'id': str(path.relative_to(HOME))}) or 3e9) + 2e9
            except ValueError:
                need = 5e9
            if shutil.disk_usage(HOME).free > need:
                _busy.add(key)
                subprocess.Popen(['brctl', 'download', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                _mark(it.get('uid'), fetched=True)


def _fetch_beats(item):
    for b in item['beats']:
        beat_path(b['f'], wait=300)
    _mark(item.get('uid'), beats_ready=True)
    _busy.discard(item.get('uid'))


def _mark(uid, **kw):
    with _lock:
        st = _load()
        for it in [st.get('current') or {}] + st.get('queue', []):
            if it.get('uid') == uid:
                it.update(kw)
        _save(st)


def _resolve_saved(item):
    resolve(item)
    key = 'tracks' if item.get('tracks') else 'records'
    _mark(item.get('uid'), **{key: item.get(key)})
    _busy.discard(item.get('uid'))
