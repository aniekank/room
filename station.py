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
    (6, 'Morning', {'yourday': 2, 'series': 4, 'crates': 2, 'tapes': 1}),
    (10, 'Daytime', {'series': 4, 'crates': 3, 'vault': 1, 'tapes': 1}),
    (13, 'FlyBoy Academy', {'course': 5, 'crates': 1, 'tapes': 1}),
    (16, 'Afternoon', {'series': 4, 'crates': 2, 'vault': 1, 'promo': 1, 'queenpin': 1}),
    (19, 'Prime Time', {'queenpin': 1, 'film': 5, 'series': 1, 'promo': 1}),
    (23, 'Late Night', {'tapes': 2, 'vault': 3, 'crates': 2, 'recording': 1, 'film': 2, 'queenpin': 1}),
]
LEAD = {'yourday', 'queenpin'}  # what opens a daypart before anything else: Your Day at 6am, Queenpin at 4pm, 7pm and 11pm
SEG_LEN = {'ident': 7, 'yourday': 80, 'vault': 6 * 100, 'crates': 3 * 75, 'tapes': 3 * 90, 'queenpin': 75}
BEATS_DEFAULT = movies.ICLOUD / 'TASK Beats Backup 2026-10-03' / 'Desktop'
BEAT_DIRS = ('Recovered beats*', 'Demo cuts*', 'California Dreamin*')  # plus the finished tracks at the top
BEAT_SKIP = ('*before-after*', '*spot*', '*EXPLICIT*', '*T.A.S.K. tag*', 'she-chose-clean*', 'She Chose - 3%*')
QUEENPIN = {'lotti-gold': 'Lotti Gold', 'mei-li': 'Mei Li', 'sable': 'Sable · The Architect', 'babi-blu': 'Babi Blu',
            'champagne': 'Champagne', 'dynasty': 'Dynasty', 'goldie': 'Goldie Knox'}  # only names the files themselves give


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
    to background apps). Small files only; the archive recording stays where it is and airs from there.
    art/logo.png (the FlyBoyRadio pin-up logo, cut out of its white background) was made once and lives in the kit."""
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
    import funk
    return _crates + funk.records()  # the funk crate grows as its covers are found


AIRED = DATA / 'crates_aired.json'  # record key -> [last aired, times aired]: what's been on, so it waits its turn
FRESH_FOR = 4 * 86400  # a record aired in the last four days stays off unless everything else has been on


def _aired():
    try:
        return json.loads(AIRED.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _mark_aired(recs):
    with _lock:
        a = _aired()
        for r in recs:
            last, n = a.get(_key(r), [0, 0])
            a[_key(r)] = [time.time(), n + 1]
        AIRED.write_text(json.dumps(a))


def _weighted(rng, recs, n, weight):
    """n records drawn by weight, no artist twice."""
    pool, out, seen = list(recs), [], set()
    while pool and len(out) < n:
        w = [weight(r) for r in pool]
        if not sum(w):
            break
        r = rng.choices(pool, w)[0]
        pool.remove(r)
        if r['artist'].lower() not in seen:
            seen.add(r['artist'].lower())
            out.append(r)
    return out


def crates_picks(rng, n=3):
    """Records for a Crates segment: ones not aired lately, funkier ones far likelier, songs already on the Mac first."""
    import funk
    recs, aired, now = crates(), _aired(), time.time()
    fresh = lambda r: now - aired.get(_key(r), [0, 0])[0] > FRESH_FOR
    w = lambda r: funk.score(r) ** 2 / (1 + aired.get(_key(r), [0, 0])[1])  # each airing halves, thirds... its chances
    ready = [r for r in recs if cached(r) and fresh(r)]
    picks = _weighted(rng, ready, n, w)
    if len(picks) < n:  # not enough on the Mac yet: the rest come down while a beat plays
        rest = [r for r in recs if fresh(r) and r not in picks and r['artist'].lower() not in {p['artist'].lower() for p in picks}]
        picks += _weighted(rng, rest or [r for r in recs if r not in picks], n - len(picks), w)
    _mark_aired(picks)
    return picks


# ---------------------------------------------------------------- YouTube for segments

BLOCKED = DATA / 'yt_blocked.json'  # videos the TV's player refused (labels often bar embedding on other sites and TVs)


def blocked():
    try:
        return set(json.loads(BLOCKED.read_text()))
    except (FileNotFoundError, ValueError):
        return set()


def block(vid):
    with _lock:
        b = blocked()
        b.add(vid)
        BLOCKED.write_text(json.dumps(sorted(b)))


def _yt(query, embeddable=True):
    """Up to five uploads of a song, best first. The TV works down the list when one is refused."""
    def build():
        hits = [e for e in sources._yt_search(query, 10) if not e['live'] and 60 <= (e['duration'] or 0) <= 1500]
        return [e['id'] for e in hits[:5]]
    try:
        vids = sources.cached('yt5:' + query.lower(), 30 * 86400, build)
    except Exception:
        return []
    bad = blocked() if embeddable else set()
    return [v for v in vids if v not in bad]


TRACKS = DATA / 'tracks'  # the Vault's and the Crates' songs, as music videos (or audio) on the Mac
INDEX = TRACKS / 'index.json'  # "artist title" -> file, so a segment can lead with what's already here
FMT = ('bestvideo[vcodec^=avc1][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]'  # H.264 + AAC: what the TV plays
       '/bestaudio[ext=m4a]/bestaudio')  # no video to be had: the song at least
_fetch = {'want': {}, 'until': 0, 'backoff': 900, 'started': False}  # query -> (priority, candidate ids)
_flock = threading.Lock()


def _key(t):
    return f"{t['artist']} {t['title']}".lower()


def _index():
    try:
        return json.loads(INDEX.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def cached(t):
    """This song's file on the Mac, or ''."""
    name = _index().get(_key(t), '')
    return name if name and (TRACKS / name).is_file() else ''


def tracks_cap():
    return 2.5e9 if shutil.disk_usage(HOME).free > 20e9 else 1e9  # more room for videos once the disk has some


def _prune_tracks():
    aired, by_file = _aired(), {v: k for k, v in _index().items()}
    # records that have already aired go first, then the oldest downloads
    files = sorted((p for p in TRACKS.glob('*') if p.name != 'index.json'),
                   key=lambda p: (by_file.get(p.name) not in aired, p.stat().st_mtime))
    total, cap = sum(p.stat().st_size for p in files), tracks_cap()
    while files and total > cap:
        p = files.pop(0)
        total -= p.stat().st_size
        p.unlink(missing_ok=True)


def track_path(name):
    p = TRACKS / Path(name).name
    return p if name and p.is_file() and p.name != 'index.json' else None


class _Pushback(Exception):
    pass


def _download(vid):
    """One music video at the best quality the TV plays (H.264 up to 1080p with AAC), or its audio if that's all there is."""
    import engine
    import yt_dlp
    TRACKS.mkdir(exist_ok=True)
    if (TRACKS / f'{vid}.mp4').is_file():
        return f'{vid}.mp4'
    extra = {}
    if settings.get('youtube_cookies_browser'):  # your own YouTube sign-in, if you've turned it on: gets past YouTube's bot check
        extra['cookiesfrombrowser'] = (settings.get('youtube_cookies_browser'),)
    try:
        with yt_dlp.YoutubeDL(engine.opts(format=FMT, merge_output_format='mp4', outtmpl=str(TRACKS / '%(id)s.%(ext)s'),
                                          max_filesize=150e6, **extra)) as ydl:
            ydl.download([f'https://www.youtube.com/watch?v={vid}'])
    except Exception as e:
        msg = str(e)
        if '429' in msg or 'not a bot' in msg or 'Too Many Requests' in msg:
            raise _Pushback(msg)
        old = TRACKS / f'{vid}.m4a'  # audio from before the videos: better than nothing
        return old.name if old.is_file() else ''
    have = [p for p in TRACKS.glob(vid + '.*') if p.suffix in ('.mp4', '.m4a', '.webm')]
    return have[0].name if have else ''


def want(t, priority):
    """Queue a song for the fetcher. Lower priority numbers go first (what's on now, then what's next)."""
    if not t.get('all') or cached(t):
        return
    with _flock:
        old = _fetch['want'].get(_key(t))
        if not old or priority < old[0]:
            _fetch['want'][_key(t)] = (priority, t['all'])
        if not _fetch['started']:
            _fetch['started'] = True
            threading.Thread(target=_fetcher, daemon=True).start()


def _fetcher():
    """One song at a time, a pause between, and a long break when YouTube pushes back: bursts are what get a Mac flagged."""
    while True:
        if shutil.disk_usage(HOME).free < 4e9:  # a full disk stops Room answering the TV: leave the space alone
            time.sleep(300)
            continue
        with _flock:
            ready = time.time() >= _fetch['until']
            job = min(_fetch['want'].items(), key=lambda kv: kv[1][0]) if ready and _fetch['want'] else None
        if not job:
            if ready and not _grow_crates_pool():
                time.sleep(5)
            continue
        key, (_, vids) = job
        name = ''
        try:
            for vid in vids:
                name = _download(vid)
                if name:
                    break
            _fetch['backoff'] = 900
        except _Pushback:
            with _flock:
                _fetch['until'] = time.time() + _fetch['backoff']
                _fetch['backoff'] = min(_fetch['backoff'] * 2, 4 * 3600)
            continue  # keep it queued for after the break
        with _flock:
            _fetch['want'].pop(key, None)
        if name:
            with _lock:
                idx = _index()
                idx[key] = name
                INDEX.write_text(json.dumps(idx))
            _prune_tracks()
        time.sleep(20)


CRATES_POOL = 25  # unaired records on the Mac; about 600 MB of music videos


def _grow_crates_pool():
    """Idle: queue one more Crates record so there are always songs ready on the Mac. Returns whether it queued one."""
    import funk
    recs, aired, now = crates(), _aired(), time.time()
    have = [r for r in recs if cached(r)]
    unplayed = [r for r in have if now - aired.get(_key(r), [0, 0])[0] > FRESH_FOR]
    if len(unplayed) >= CRATES_POOL:
        return False
    if len(have) >= CRATES_POOL or shutil.disk_usage(HOME).free < 6e9:
        # full: let the record aired longest ago go, so the pool keeps turning over without using more disk
        gone = [r for r in have if r not in unplayed]
        if not gone or shutil.disk_usage(HOME).free < 4.5e9:
            return False
        old = min(gone, key=lambda r: aired[_key(r)][0])
        track_path(cached(old)).unlink(missing_ok=True)
    fresh = [r for r in recs if not cached(r) and now - aired.get(_key(r), [0, 0])[0] > FRESH_FOR and _key(r) not in _fetch['want']]
    for r in _weighted(random, fresh, 8, lambda r: funk.score(r) ** 2 / (1 + aired.get(_key(r), [0, 0])[1])):
        if not cached(r):
            t = dict(r)
            t['all'] = _yt(f"{t['artist']} {t['title']}", embeddable=False)
            if t['all']:
                want(t, 10000)  # behind anything a segment is waiting for
                return True
    return False


def fetch_status():
    with _flock:
        return {'queued': len(_fetch['want']), 'paused_for': max(0, int(_fetch['until'] - time.time())),
                'on_mac': len(_index())}


def resolve(item):
    """Find a segment's songs on YouTube (a search, light on YouTube) and attach any already on the Mac."""
    for t in item.get('tracks') or item.get('records') or []:
        if not t.get('all'):
            t['all'] = _yt(f"{t['artist']} {t['title']}", embeddable=False)
            bad = blocked()
            t['vids'] = [v for v in t['all'] if v not in bad]
            t['vid'] = t['vids'][0] if t['vids'] else ''
        t['media'] = cached(t)


def lead_with_cached(lst):
    """Songs already on the Mac first, so a segment put on now starts with sound."""
    lst.sort(key=lambda t: not cached(t))
    return lst


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
    import ready
    return (HOME / m_id).is_file() or bool(ready.path(m_id))


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


def pick(kind, st, rng, ref=None):
    """A program of this kind. ref picks a particular one: a show or course by name (its next episode), a film by id,
    a Vault show by date, a promo by file."""
    lib = [m for m in movies.scan()['movies'] if m['plays']]
    aired = st.setdefault('aired', {})
    if kind in ('series', 'course'):
        by = _shows_of(lib, kind)
        if not by or (ref and ref not in by):
            return None
        names = sorted(by)
        if ref:
            g = ref
        else:
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
        if ref:
            m = next((f for f in films if f['id'] == ref), None)
            if m:
                aired[m['id']] = time.time()
            return _video(m, st) if m else None
        fresh = [m for m in films if time.time() - aired.get(m['id'], 0) > 30 * 86400] or films
        if not fresh:
            return None
        ready = [m for m in fresh if _ready(m['id'])]
        m = rng.choice(ready if ready and rng.random() < 0.5 else fresh)  # half the time, whatever's on the Mac
        aired[m['id']] = time.time()  # booked: don't book it again this month
        return _video(m, st)
    if kind == 'promo':
        p = kit_files('promos', '*.mp4')
        if ref in p:
            p = [ref]
        return {'kind': 'promo', 'src': rng.choice(p), 'title': _promo_title(p[0] if ref else ''), 'dur': 60} if p else None
    if kind == 'recording':
        rec = settings.get('station_recording')
        return {'kind': 'recording', 'path': rec, 'title': 'FlyBoyRadio, live on WMUC', 'dur': 3 * 3600,
                'show': _show_for_recording(rec)} if rec else None
    if kind == 'vault':
        s = next((x for x in shows() if x['date'] == ref), None) if ref else pick_show(rng)
        if not s:
            return None
        tracks = [dict(t) for t in s['tracks'] if not t['own']]
        if not tracks:
            return None
        rng.shuffle(tracks)
        tracks = lead_with_cached(tracks[:6])
        return {'kind': 'vault', 'beats': some_beats(rng, 1), 'title': f"FlyBoyRadio Vault · {s['label']}", 'date': s['date'], 'label': s['label'],
                'all': [f"{t['artist']}: {t['title']}" for t in s['tracks']][:24], 'tracks': tracks[:6], 'per': 100,
                'dur': 100 * min(6, len(tracks))}
    if kind == 'crates':
        recs = crates()
        if not recs:
            return None
        picks = lead_with_cached([dict(r) for r in crates_picks(rng)])
        return {'kind': 'crates', 'title': 'From the Crates', 'records': picks, 'beats': some_beats(rng, 1), 'per': 75, 'dur': 75 * len(picks)}
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
    if item.get('kind') == 'video' and (item.get('fetched') or item.get('id') in _load().get('shelf', [])):
        subprocess.Popen(['brctl', 'evict', str(HOME / item['id'])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _advance(st, now):
    if st.get('current'):
        _finished(st['current'])
    start = (st['current']['start'] + st['current']['dur']) if st.get('current') else now
    q = st['queue']
    nxt = q.pop(0)
    if nxt['kind'] in ('video', 'recording') and not _item_ready(nxt):
        nxt['bumped'] = nxt.get('bumped', 0) + 1
        if nxt['bumped'] <= (10 if nxt.get('asked') else 4):  # something you asked for gets ~40 minutes to come down
            nxt['fetched'] = False  # and iCloud gets asked again
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
    waiting = None  # something you asked for, still coming down from iCloud
    if q and q[0].get('asked') and q[0]['kind'] == 'video' and not _item_ready(q[0]):
        waiting = {'title': q[0]['title'], 'pct': icloud_progress(HOME / q[0]['id']), 'on_power': on_power()}
    return {'now': t, 'item': cur, 'offset': t - cur['start'], 'next': nexts, 'waiting': waiting,
            'daypart': daypart(t)[1], 'ends': cur['start'] + cur['dur']}


_brctl = {'at': 0, 'text': ''}


def icloud_progress(path):
    """How far iCloud has got bringing a file down, 0-100, or None if it isn't downloading. brctl's status hides names
    but shows each item's exact size in bytes, which matches the placeholder's."""
    p = Path(path)
    try:
        size = plistlib.loads((p.parent / f'.{p.name}.icloud').read_bytes()).get('NSURLFileSizeKey')
    except (OSError, ValueError):
        return 100 if p.is_file() else None
    if time.time() - _brctl['at'] > 8:
        try:
            out = subprocess.run(['brctl', 'status', 'com.apple.CloudDocs'], capture_output=True, text=True, timeout=20).stdout
            _brctl.update(at=time.time(), text=re.sub(r'\x1b\[[0-9;]*m', '', out))
        except subprocess.SubprocessError:
            return None
    lines, seen = _brctl['text'].splitlines(), False
    for i, line in enumerate(lines):  # an item shows up more than once; the entry with the downloader has the percentage
        if f'({size})' in line:
            seen = True
            m = re.search(r'downloading:([0-9.]+)%', ' '.join(lines[i:i + 3]))
            if m:
                return round(float(m.group(1)))
    return 0 if seen else None


def on_power():
    try:
        return "'AC Power'" in subprocess.run(['pmset', '-g', 'batt'], capture_output=True, text=True, timeout=5).stdout
    except subprocess.SubprocessError:
        return True


SHELF_MAX = 6


def pick_waiting():
    """Is something you asked for still coming down? Then nothing else should compete for a slow connection."""
    q = _load().get('queue', [])
    return bool(q and q[0].get('asked') and q[0]['kind'] == 'video' and not _item_ready(q[0]))


def _keep_shelf(log):
    """While the Mac is on power and has room: the next episode of each show and a couple of films come down ahead, so
    On Demand has things that play the moment you pick them. iCloud crawls on battery, so this waits for the charger."""
    rng = random.Random()
    while True:
        try:
            import ready
            if on_power() and not pick_waiting() and not ready.busy():  # one thing on iCloud at a time
                with _lock:
                    st = _load()
                shelf = [i for i in st.get('shelf', []) if (HOME / i).exists() or (HOME / i).parent.joinpath(f'.{Path(i).name}.icloud').exists()]
                lib = [m for m in movies.scan()['movies'] if m['plays']]
                want_ids = []
                for name, eps in sorted(_shows_of(lib, 'series').items()):
                    want_ids.append(eps[st.get('next_ep', {}).get(name, 0) % len(eps)]['id'])
                # films are ready.py's job now: small copies that fit the disk, not the full originals
                coming = [i for i in shelf if not _ready(i)]
                for mid in want_ids:
                    if len(shelf) >= SHELF_MAX or coming:  # one at a time: on a slow connection, several at once each crawl
                        break
                    if mid in shelf or _ready(mid):
                        continue
                    size = _cloud_size({'id': mid}) or 3e9
                    if shutil.disk_usage(HOME).free - size < 6e9:  # always leave 6 GB: a full disk stops the TV
                        break
                    subprocess.Popen(['brctl', 'download', str(HOME / mid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    shelf.append(mid)
                    coming.append(mid)
                    log(f'station: shelf: bringing down {Path(mid).name}')
                with _lock:
                    st = _load()
                    st['shelf'] = shelf
                    _save(st)
        except Exception as e:
            log(f'station: shelf: {e}')
        time.sleep(600)


def keep_shelf(log=print):
    threading.Thread(target=_keep_shelf, args=(log,), daemon=True).start()


def art_for(item):
    """A picture for what's on: a film's or show's poster, a record cover, the segment's own art, or the logo."""
    import art
    k = item.get('kind')
    if k == 'video':
        m = next((x for x in movies.scan()['movies'] if x['id'] == item.get('id')), None)
        if m and art.for_movie(m):
            return art.for_movie(m)
    if k == 'crates' and item.get('records'):
        return (item['records'][0].get('img') or '').replace('ab67616d00004851', 'ab67616d0000b273')
    if k == 'queenpin' and item.get('slides'):
        return '/station/kit/' + item['slides'][1 if len(item['slides']) > 1 else 0]['img']
    if k == 'tapes' and item.get('slides'):
        return '/station/kit/' + next((x for x in item['slides'] if '/drive/' in x), item['slides'][0])
    if k in ('vault', 'recording'):
        return '/station/kit/art/flyboyradio-01.png'
    return '/station/kit/art/logo.png'


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


ON_DEMAND = ('queenpin', 'tapes', 'vault', 'crates', 'yourday', 'series', 'course', 'film', 'promo', 'recording')


def _promo_title(src):
    name = Path(src).stem.replace('-16x9', '').replace('-', ' ').strip()
    return name.title() if name else 'FlyBoy[TV] presents'


def play_now(kind, ref=None):
    """From the remote: put anything on now. What was on ends here and the schedule carries on after it.
    Something still in iCloud starts as soon as it's down; a short Crates segment covers the wait."""
    if kind not in ON_DEMAND:
        return None
    rng, waiting = random.Random(), False
    with _lock:
        st = _load()
        item = pick(kind, st, rng, ref)
        if not item:
            return None
        if st.get('current'):
            _finished(st['current'])
        item['uid'] = uuid.uuid4().hex[:10]
        item['asked'] = True
        st.setdefault('queue', [])
        if item['kind'] in ('video', 'recording') and not _item_ready(item):
            filler = pick('crates', st, rng) or {'kind': 'ident', 'title': 'FlyBoy[TV]', 'dur': 7}
            filler['uid'] = uuid.uuid4().hex[:10]
            st['current'] = _stamp(filler, time.time())
            st['queue'].insert(0, item)
            waiting = True
        else:
            st['current'] = _stamp(item, time.time())
            _air(st, item)
        _save(st)
        cur, q = st['current'], st['queue']
    _prepare(cur, q[:2])
    return {'ok': True, 'title': item['title'], 'waiting': waiting}


def library():
    """Everything FlyBoy[TV] can put on, for the on-demand menus."""
    lib = [m for m in movies.scan()['movies'] if m['plays']]
    nxt = _load().get('next_ep', {})

    def runs(kind):
        out = []
        for name, eps in sorted(_shows_of(lib, kind).items()):
            ep = eps[nxt.get(name, 0) % len(eps)]
            import art
            f = art.poster(name, 'show') if kind == 'series' else ''
            out.append({'ref': name, 'title': name, 'sub': f"Next: {ep['title']} · {len(eps)} episodes" if kind == 'series'
                        else f"Next: {ep['title']} · {len(eps)} lessons", 'ready': _ready(ep['id']), 'poster': f'/poster/{f}' if f else ''})
        return out
    import art
    films = sorted(({'ref': m['id'], 'title': m['title'], 'ready': _ready(m['id']), 'poster': art.for_movie(m)}
                    for m in lib if m['group'] == 'Films'), key=lambda f: f['title'].lower())
    segs = [('queenpin', 'Queenpin: Era One', 'The cast, cut to one of your beats'),
            ('tapes', 'Ride With Me', 'Three beats over the night drive'),
            ('vault', 'FlyBoyRadio Vault', 'A show from this week of the year'),
            ('crates', 'From the Crates', 'Three records from the digging list'),
            ('yourday', 'Your Day', 'Calendar, to-dos, notes, Keys and weather'),
            ('recording', 'FlyBoyRadio, live on WMUC', 'The 6 Feb 2011 show, all three hours')]
    def ready_first(rows):  # what's already on the Mac plays the moment you pick it, so it goes on top
        for r in rows:
            r['sub'] = ('▶ plays now · ' if r['ready'] else 'downloads from iCloud first · ') + r.get('sub', '')
        return sorted(rows, key=lambda r: not r['ready'])
    return {
        'segments': [{'kind': k, 'title': t, 'sub': d} for k, t, d in segs if k != 'recording' or settings.get('station_recording')] +
                    [{'kind': 'promo', 'ref': p, 'title': _promo_title(p), 'sub': 'Promo'} for p in kit_files('promos', '*.mp4')],
        'series': ready_first([dict(x, kind='series') for x in runs('series')]),
        'academy': ready_first([dict(x, kind='course') for x in runs('course')]),
        'films': ready_first([dict(x, kind='film', sub='') for x in films]),
        'vault': [{'kind': 'vault', 'ref': v['date'], 'title': v['label'], 'sub': f"{len(v['tracks'])} tracks"} for v in shows()],
    }


_busy = set()


def _prepare(cur, q):
    """In the background: download what's coming up from iCloud and look up YouTube ids for segments."""
    for pos, it in enumerate([cur] + q[:8]):  # songs eight programs ahead; downloads three
        key = it.get('uid') or id(it)
        if it['kind'] in ('vault', 'crates'):
            lst = it.get('tracks') or it.get('records') or []
            if any(not t.get('all') for t in lst):
                if key not in _busy:
                    _busy.add(key)
                    threading.Thread(target=_resolve_saved, args=(it, pos), daemon=True).start()
                continue
            changed = False
            for j, t in enumerate(lst):  # pick up songs the fetcher has brought down since
                m = cached(t)
                if m != t.get('media'):
                    t['media'], changed = m, True
                if not m:
                    want(t, pos * 10 + j)
            if changed:
                _mark(it.get('uid'), **{'tracks' if it.get('tracks') else 'records': lst})
            continue
        if key in _busy or pos > 3:
            continue
        if it.get('beats') and not it.get('beats_ready'):  # bring the beats down from iCloud ahead of airtime
            _busy.add(key)
            threading.Thread(target=_fetch_beats, args=(it,), daemon=True).start()
            continue
        if it['kind'] in ('video', 'recording') and not _item_ready(it) and not it.get('fetched'):
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


def _resolve_saved(item, pos=0):
    resolve(item)
    key = 'tracks' if item.get('tracks') else 'records'
    for j, t in enumerate(item.get(key) or []):
        if not t.get('media'):
            want(t, pos * 10 + j)
    _mark(item.get('uid'), **{key: item.get(key)})
    _busy.discard(item.get('uid'))
