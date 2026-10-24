"""Makes MKV, AVI and MPG files playable on the TV by writing an MP4 next to each one.

What the 2018 Tizen browser plays (tested on a UN32M4500): H.264 and HEVC video, 8- and 10-bit, in MP4 or MKV.
It can't do XviD/DivX (AVI), and Samsung dropped DTS that year, so to be safe:
  video  H.264 / HEVC  -> copied as is (fast, no quality lost)
         anything else -> H.264 at up to 720p on the Mac's hardware encoder
  audio  AAC / MP3     -> copied;  anything else -> stereo AAC (the English track when there's a choice)

One file at a time, because the disk is the limit: bring the original down from iCloud, convert, let the
original go back to the cloud, wait for the MP4 to upload, then let that go too. Originals are never touched.
Turned on with "convert_videos": true; the server runs it in the background (room convert runs it in Terminal).
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import movies
import settings
from paths import DATA

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
ICLOUD_JS = ROOT / 'scripts' / 'icloud.js'
STATE = DATA / 'convert.json'
TMP = DATA / 'convert-tmp'  # same disk as iCloud Drive, so the finished file moves in instantly, but never syncs half-written
TODO = {'.mkv', '.avi', '.mpg', '.mpeg', '.wmv'}
MARGIN = 3e9  # always leave this much free on the disk


def _bin(name):
    for p in (shutil.which(name), f'/opt/homebrew/bin/{name}', f'/usr/local/bin/{name}'):
        if p and Path(p).exists():
            return p
    return None


def _load():
    try:
        return json.loads(STATE.read_text())
    except (FileNotFoundError, ValueError):
        return {'done': {}, 'failed': {}, 'now': None}


def _save(st):
    STATE.write_text(json.dumps(st, indent=1))


def twin(src):
    """Where a file's MP4 goes: same folder, same name."""
    out = src.with_suffix('.mp4')
    return out if not out.exists() or out.stat().st_size == 0 else src.with_name(src.stem + ' (TV).mp4')


def _stub(p):
    return p.parent / f'.{p.name}.icloud'


def _size(p):
    if p.exists():
        return p.stat().st_size
    try:
        import plistlib
        return plistlib.loads(_stub(p).read_bytes()).get('NSURLFileSizeKey', 0)
    except (OSError, ValueError):
        return 0


def _icloud(p):
    try:
        r = subprocess.run(['osascript', '-l', 'JavaScript', str(ICLOUD_JS), str(p)], capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout or '{}')
    except (subprocess.SubprocessError, ValueError):
        return {}


def todo():
    """Videos in your folders the TV can't play yet and that have no MP4 twin, smallest first."""
    st = _load()
    out = []
    for m in movies.scan()['movies']:
        p = movies.HOME / m['id']
        if p.suffix.lower() not in TODO or m['id'] in st['done'] or st['failed'].get(m['id'], {}).get('tries', 0) >= 2:
            continue
        if p.with_suffix('.mp4').exists() or _stub(p.with_suffix('.mp4')).exists():
            continue
        out.append((p, _size(p), m))
    out.sort(key=lambda x: x[1])
    return out


def probe(p):
    r = subprocess.run([_bin('ffprobe'), '-v', 'error', '-show_streams', '-of', 'json', str(p)], capture_output=True, text=True, timeout=120)
    return json.loads(r.stdout or '{}').get('streams', [])


def plan(streams):
    """The ffmpeg arguments for one file, from what's inside it."""
    vids = [s for s in streams if s.get('codec_type') == 'video' and s.get('disposition', {}).get('attached_pic') != 1]
    auds = [s for s in streams if s.get('codec_type') == 'audio']
    if not vids:
        return None
    v = vids[0]
    eng = [s for s in auds if (s.get('tags') or {}).get('language', '').lower() in ('eng', 'en')]
    a = (eng or auds or [None])[0]
    args = ['-map', f"0:{v['index']}"] + (['-map', f"0:{a['index']}"] if a else [])
    if v.get('codec_name') in ('h264', 'hevc'):
        args += ['-c:v', 'copy'] + (['-tag:v', 'hvc1'] if v['codec_name'] == 'hevc' else [])
    else:
        w = min(1280, int(v.get('width') or 1280))
        kbps = max(600, min(2800, int(w * 2.2)))  # 720p gets 2.8 Mbps; a 352-wide AVI doesn't need more than its own size
        args += ['-c:v', 'h264_videotoolbox', '-b:v', f'{kbps}k', '-maxrate', f'{int(kbps * 1.4)}k', '-profile:v', 'high',
                 '-vf', "scale='min(1280,iw)':-2,format=yuv420p"]
    if a:
        args += ['-c:a', 'copy'] if a.get('codec_name') in ('aac', 'mp3') else ['-c:a', 'aac', '-b:a', '192k', '-ac', '2']
    return args + ['-sn', '-dn', '-movflags', '+faststart']


def _wait(cond, timeout, every=5, stop=None):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        if stop and stop.is_set():
            return False
        time.sleep(every)
    return False


def one(p, size, log, stop=None):
    """Convert one file. Returns the MP4's path, or raises with what went wrong."""
    was_cloud = not p.exists()
    if was_cloud:
        subprocess.run(['brctl', 'download', str(p)], capture_output=True)
        if not _wait(lambda: p.exists() and _icloud(p).get('local'), max(600, size / 2e6), 10, stop):
            raise RuntimeError('download did not finish')
    out = twin(p)
    TMP.mkdir(exist_ok=True)
    tmp = TMP / 'part.mp4'
    args = plan(probe(p))
    if not args:
        raise RuntimeError('no video stream')
    t0 = time.time()
    r = subprocess.run([_bin('ffmpeg'), '-nostdin', '-v', 'error', '-y', '-i', str(p), *args, str(tmp)], capture_output=True, text=True)
    if r.returncode or not tmp.exists() or tmp.stat().st_size < 1e6:
        tmp.unlink(missing_ok=True)
        raise RuntimeError((r.stderr or 'ffmpeg failed').strip().splitlines()[-1][:200])
    shutil.move(str(tmp), str(out))
    log(f'convert: {p.name} -> {out.name} in {int(time.time() - t0)}s ({"copy" if "copy" in args[args.index("-c:v") + 1] else "encode"})')
    if was_cloud:  # put the original back the way it was
        subprocess.run(['brctl', 'evict', str(p)], capture_output=True)
    return out


def _release(out, stop):
    """Once the MP4 is safely in iCloud, the Mac doesn't need to keep it."""
    if _wait(lambda: _icloud(out).get('uploaded'), 12 * 3600, 30, stop):
        subprocess.run(['brctl', 'evict', str(out)], capture_output=True)


def run(log=print, stop=None, once=False):
    if not (_bin('ffmpeg') and _bin('ffprobe')):
        log('convert: needs ffmpeg (brew install ffmpeg)')
        return
    while not (stop and stop.is_set()):
        st = _load()
        try:
            import station
            import ready
            if station.pick_waiting() or ready.busy():  # something you asked for is coming down: don't split the connection with it
                time.sleep(120)
                continue
        except Exception:
            pass
        free = shutil.disk_usage(movies.HOME).free
        job = next(((p, s, m) for p, s, m in todo() if s * 2 + MARGIN < free), None)
        if not job:
            st['now'] = None
            st['waiting'] = len(todo())
            _save(st)
            if once:
                return
            time.sleep(600)  # nothing fits yet: space frees up as uploads finish
            continue
        p, size, m = job
        st['now'] = {'id': m['id'], 'title': m['title'], 'size': size, 'since': time.time()}
        _save(st)
        try:
            out = one(p, size, log, stop)
            st = _load()
            st['done'][m['id']] = {'mp4': str(out.relative_to(movies.HOME)), 'at': time.time()}
            st['failed'].pop(m['id'], None)
            threading.Thread(target=_release, args=(out, stop), daemon=True).start()
        except Exception as e:  # keep going with the rest; try this one again later
            st = _load()
            f = st['failed'].setdefault(m['id'], {'tries': 0})
            f.update(tries=f['tries'] + 1, error=str(e)[:200], at=time.time())
            log(f'convert: {p.name} failed: {e}')
        st['now'] = None
        _save(st)
        if once:
            return


def status():
    st = _load()
    left = todo()
    return {'now': st.get('now'), 'done': len(st['done']), 'failed': {k: v for k, v in st['failed'].items()},
            'left': len(left), 'left_gb': round(sum(s for _, s, _ in left) / 1e9, 1),
            'free_gb': round(shutil.disk_usage(movies.HOME).free / 1e9, 1), 'on': bool(settings.get('convert_videos'))}


def start(log=print):
    if settings.get('convert_videos'):
        threading.Thread(target=run, kwargs={'log': log}, daemon=True).start()
