"""Films kept on the Mac, ready to play the moment you pick them.

The library lives in iCloud and the disk is nearly full, so a film can't come down when you ask for it. Instead a few
are kept here as small copies: H.264 720p (the TV's panel is 1366x768, so nothing is lost on screen) at about a third
of the original's size. One at a time: bring the original down, make the copy, let the original go back to iCloud.
The films you pick on the phone come first; unwatched films fill the rest.
"""
import json
import random
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import movies
from paths import DATA

DIR = DATA / 'ready'
STATE = DATA / 'ready.json'  # {'picks': [ids], 'files': {id: file}, 'now': {...} or None}
KEEP = 3  # films kept ready, as many as the disk allows
MARGIN = 1.5e9  # what's always left free while working: a full disk stops the TV loading anything
VIDEO_KBPS = 1500  # the Mac's encoder lands nearer 1.9 Mbps for this
BYTES_PER_SEC = (VIDEO_KBPS * 1.3 + 160) * 125  # with the audio: about 0.95 GB an hour
_lock = threading.Lock()
_busy = threading.Event()


def _load():
    try:
        st = json.loads(STATE.read_text())
    except (FileNotFoundError, ValueError):
        st = {}
    st.setdefault('picks', [])
    st.setdefault('files', {})
    st.setdefault('now', None)
    return st


def _save(st):
    STATE.write_text(json.dumps(st, indent=1))


def path(movie_id):
    """The ready copy of a film, or None."""
    name = _load()['files'].get(movie_id)
    p = DIR / name if name else None
    return p if p and p.is_file() else None


def _local(m):
    """A film that's already on the Mac and plays on the TV counts as ready as it is."""
    return not m['cloud'] and m['plays']


def ready_ids():
    return {k for k, v in _load()['files'].items() if (DIR / v).is_file()} | {m['id'] for m in _films() if _local(m)}


def busy():
    """Making a copy now: the converter and the shelf keep off iCloud meanwhile."""
    return _busy.is_set()


def pick(movie_id, keep=True):
    """From the phone: keep this film ready (it goes to the front), or stop keeping it."""
    with _lock:
        st = _load()
        st['picks'] = [i for i in st['picks'] if i != movie_id]
        if keep:
            st['picks'].insert(0, movie_id)
        _save(st)


def status():
    st = _load()
    return {'picks': st['picks'], 'ready': sorted(ready_ids()), 'now': st['now'], 'keep': KEEP,
            'free_gb': round(shutil.disk_usage(movies.HOME).free / 1e9, 1)}


def _films():
    return [m for m in movies.scan()['movies'] if m['group'] == 'Films']


def _wanted(films, st):
    """The films that should be ready, in order: your picks, then unwatched films (a fixed shuffle, so it doesn't churn)."""
    ids = {m['id'] for m in films}
    out = [i for i in st['picks'] if i in ids][:KEEP]
    have = [i for i in st['files'] if i in ids and i not in out and (DIR / st['files'][i]).is_file()]
    out += have[:KEEP - len(out)]  # copies already made stay until a pick needs the room
    fresh = [m['id'] for m in films if not m['t'] and m['id'] not in out]
    random.Random(len(films)).shuffle(fresh)
    return out + fresh[:max(0, KEEP - len(out))]


def _drop(st, movie_id, log):
    name = st['files'].pop(movie_id, None)
    if name:
        (DIR / name).unlink(missing_ok=True)
        log(f'ready: let {Path(movie_id).name} go')


def _cloud_size(p):
    import convert
    return convert._size(p)


def _wait(cond, timeout, every=10):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(every)
    return False


def _make(m, log):
    """Bring the film down, write the 720p copy, send the original back to iCloud. Returns the copy's file name."""
    import convert
    p = movies.HOME / m['id']
    was_cloud = not p.is_file()
    if was_cloud:
        subprocess.run(['brctl', 'download', str(p)], capture_output=True, timeout=60)
        size = _cloud_size(p) or 3e9
        if not _wait(lambda: p.is_file() and convert._icloud(p).get('local'), max(1800, size / 4e5)):
            raise RuntimeError('iCloud did not finish bringing it down')
    name = re.sub(r'[^a-z0-9]+', '-', m['title'].lower()).strip('-')[:60] + '.mp4'
    DIR.mkdir(exist_ok=True)
    if m['plays'] and p.stat().st_size <= (m.get('duration') or 7200) * BYTES_PER_SEC:  # already small and plays: keep it as is
        # an APFS clone: shares the original's blocks, so it costs no space, and keeps them when iCloud lets the original go
        subprocess.run(['cp', '-c', str(p), str(DIR / '.part.mp4')], check=True, capture_output=True, timeout=600)
        shutil.move(str(DIR / '.part.mp4'), str(DIR / name))
        if was_cloud or convert._icloud(p).get('uploaded'):
            subprocess.run(['brctl', 'evict', str(p)], capture_output=True, timeout=60)
        log(f'ready: {m["title"]} ready as it is, {round((DIR / name).stat().st_size / 1e9, 1)} GB')
        return name
    streams = convert.probe(p)
    vids = [s for s in streams if s.get('codec_type') == 'video' and s.get('disposition', {}).get('attached_pic') != 1]
    auds = [s for s in streams if s.get('codec_type') == 'audio']
    if not vids:
        raise RuntimeError('no video in the file')
    eng = [s for s in auds if (s.get('tags') or {}).get('language', '').lower() in ('eng', 'en')]
    a = (eng or auds or [None])[0]
    tmp = DIR / '.part.mp4'
    args = [convert._bin('ffmpeg'), '-nostdin', '-v', 'error', '-y', '-i', str(p), '-map', f"0:{vids[0]['index']}"]
    args += ['-map', f"0:{a['index']}", '-c:a', 'aac', '-b:a', '160k', '-ac', '2'] if a else []
    args += ['-c:v', 'h264_videotoolbox', '-b:v', f'{VIDEO_KBPS}k', '-maxrate', f'{int(VIDEO_KBPS * 1.5)}k', '-profile:v', 'high',
             '-vf', "scale='min(1280,iw)':-2,format=yuv420p", '-sn', '-dn', '-movflags', '+faststart', str(tmp)]
    t0 = time.time()
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode or not tmp.is_file() or tmp.stat().st_size < 50e6:
        tmp.unlink(missing_ok=True)
        raise RuntimeError((r.stderr or 'ffmpeg failed').strip().splitlines()[-1][:200])
    shutil.move(str(tmp), str(DIR / name))
    if was_cloud or convert._icloud(p).get('uploaded'):  # it's safe in iCloud: the Mac doesn't need the big one
        subprocess.run(['brctl', 'evict', str(p)], capture_output=True, timeout=60)
    log(f'ready: {m["title"]} ready in {int((time.time() - t0) / 60)} min, {round((DIR / name).stat().st_size / 1e9, 1)} GB')
    return name


def _worker(log):
    import station
    failed = {}
    with _lock:  # a restart mid-copy leaves this behind
        st = _load()
        st['now'] = None
        _save(st)
    while True:
        try:
            films = _films()
            byid = {m['id']: m for m in films}
            with _lock:
                st = _load()
                want = _wanted(films, st)
                for i in [i for i in st['files'] if i not in want]:  # no longer wanted: free its space
                    _drop(st, i, log)
                _save(st)
            todo = [i for i in want if not path(i) and not _local(byid[i]) and time.time() - failed.get(i, 0) > 6 * 3600]
            if todo and station.on_power() and not station.pick_waiting():  # iCloud crawls on battery
                def need(i):
                    p = movies.HOME / i
                    return (0 if p.is_file() else _cloud_size(p) or 3e9) + (byid[i].get('duration') or 7200) * BYTES_PER_SEC + MARGIN
                free = shutil.disk_usage(movies.HOME).free
                fits = next((i for i in todo if need(i) <= free), None)
                if not fits:  # no room: a copy you didn't pick makes way for one you did
                    with _lock:
                        st = _load()
                        spare = [i for i in st['files'] if i not in st['picks']] if todo[0] in st['picks'] else []
                        if spare:
                            _drop(st, spare[-1], log)
                            _save(st)
                            continue
                else:
                    m = byid[fits]
                    _busy.set()
                    with _lock:
                        st = _load()
                        st['now'] = {'id': m['id'], 'title': m['title'], 'since': time.time()}
                        _save(st)
                    try:
                        name = _make(m, log)
                        with _lock:
                            st = _load()
                            st['files'][m['id']] = name
                            _save(st)
                    except Exception as e:
                        failed[m['id']] = time.time()
                        log(f'ready: {m["title"]}: {e}')
                    finally:
                        _busy.clear()
                        with _lock:
                            st = _load()
                            st['now'] = None
                            _save(st)
                    continue
        except Exception as e:
            log(f'ready: {e}')
        time.sleep(120)


def start(log=print):
    threading.Thread(target=_worker, args=(log,), daemon=True).start()
