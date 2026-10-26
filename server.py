"""Room's local server: serves the TV channels, the phone remote, and a tiny command bus.

The TV page polls /api/poll every second; the phone remote POSTs /api/cmd. That keeps
the TV side to plain fetch() so the 2018-19 Tizen browser can run it.
"""
import json
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import art
import convert
import dig
import movies
import personal
import ready
import settings
import sources
import station
from paths import DATA

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))  # _MEIPASS: inside Room.app
WEB = ROOT / 'web'
PORT = int(os.environ.get('ROOM_PORT', 8788))
MEDIA = {'.m4a': 'audio/mp4', '.webm': 'audio/webm', '.opus': 'audio/ogg', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4', '.png': 'image/png', '.jpg': 'image/jpeg',
         '.jpeg': 'image/jpeg', '.json': 'application/json', '.md': 'text/markdown; charset=utf-8'}

_lock = threading.Lock()
_queue = []          # commands waiting for the TV
_tv_state = {}       # what the TV last reported (channel, video, time...)
_tv_seen = 0.0


def _jsonl_append(name, row):
    DATA.mkdir(exist_ok=True)
    with open(DATA / name, 'a') as f:
        f.write(json.dumps(row) + '\n')


def _jsonl(name):
    try:
        return [json.loads(l) for l in (DATA / name).read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def practice_summary():
    rows = _jsonl('practice.jsonl')
    days = sorted({r['date'] for r in rows if r.get('minutes', 0) >= 15})
    streak, d = 0, datetime.now().date()
    from datetime import timedelta
    if d.isoformat() not in days:
        d -= timedelta(days=1)  # today not done yet doesn't break the streak
    while d.isoformat() in days:
        streak += 1
        d -= timedelta(days=1)
    return {'streak': streak, 'total_days': len(days), 'today': datetime.now().date().isoformat() in days,
            'last': rows[-5:]}


def save_dig_moment(note=''):
    st = dict(_tv_state)
    if st.get('channel') != 'dig' or not st.get('video'):
        return None
    t = max(0, int(st.get('t', 0)) - 6)  # you hear it, then reach for the phone
    row = {'at': datetime.now().isoformat(timespec='seconds'), 'id': st['video'], 't': t,
           'title': st.get('title', ''), 'lane': st.get('lane', ''), 'note': note,
           'url': f"https://youtu.be/{st['video']}?t={t}"}
    _jsonl_append('dig_saves.jsonl', row)
    _export_saves()
    dig.saved(st['video'])
    return row


def _export_saves():
    rows = _jsonl('dig_saves.jsonl')
    lines = ['# Dig Tube saves', '', 'Moments flagged from the TV. Timestamps start ~6s before you hit Save.', '']
    for r in reversed(rows):
        m, s = divmod(r['t'], 60)
        lines.append(f"- [{r['title']}]({r['url']}) at {m}:{s:02d} ({r['lane']}, saved {r['at'][:16].replace('T', ' ')})"
                     + (f" - {r['note']}" if r.get('note') else ''))
    (DATA / 'Dig Saves.md').write_text('\n'.join(lines) + '\n')


def _any_clip():
    """A clip from Dig Tube's pool for the home tile, without counting it as played (dig.pick() would)."""
    import random
    clips = list(dig.load()['clips'].values())
    return random.choice(clips)['id'] if clips else ''


def home_summary():
    """Everything the home screen shows, in one request: what's on FlyBoy[TV] (with art), today's city, the latest
    Dig clip, the Keys streak and a few posters for Movies."""
    out = {'practice': practice_summary()}
    try:
        n = station.now()
        it = n['item']
        out['station'] = {'title': it['title'], 'kind': it['kind'], 'show': it.get('show', ''), 'art': station.art_for(it),
                          'progress': round(n['offset'] / max(1, it['dur']), 3), 'daypart': n['daypart'],
                          'next': next((x['title'] for x in n['next'] if x['kind'] != 'ident'), '')}
    except Exception:
        out['station'] = None
    try:
        cid = sources.DAY_CITY[datetime.now().weekday()]
        c = sources.city_payload(cid)
        out['city'] = {'name': c['name'], 'tz': c['tz'], 'weather': c.get('weather'),
                       'view': (c.get('views') or [{}])[0].get('id', '')}
    except Exception:
        out['city'] = None
    saves = _jsonl('dig_saves.jsonl')
    out['dig'] = {'saves': len(saves), 'last': saves[-1] if saves else None,
                  'clip': saves[-1]['id'] if saves else _any_clip()}
    try:
        import art
        ms = movies.scan()['movies']
        started = [m for m in ms if 0 < m['t'] < m['duration'] - 120]
        posters = [art.for_movie(m) for m in started + ms]
        out['movies'] = {'count': len(ms), 'continue': len(started), 'posters': [p for p in dict.fromkeys(posters) if p][:6]}
    except Exception:
        out['movies'] = {'count': 0, 'continue': 0, 'posters': []}
    return out


def qr_svg(text):
    try:
        import qrcode
    except ImportError:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>'
    q = qrcode.QRCode(border=2)
    q.add_data(text)
    q.make(fit=True)
    m = q.get_matrix()
    cells = ''.join(f'M{x},{y}h1v1h-1z' for y, row in enumerate(m) for x, on in enumerate(row) if on)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {len(m)} {len(m)}" shape-rendering="crispEdges">'
            f'<rect width="100%" height="100%" fill="#fff"/><path d="{cells}" fill="#000"/></svg>')


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    def log_message(self, fmt, *args):
        line = str(args[0]) if args else ''
        if '/api/poll' not in line and '/api/tv ' not in line and '/api/state' not in line and '/media' not in line:
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        try:
            return json.loads(self.rfile.read(n) or b'{}')
        except json.JSONDecodeError:
            return {}

    def _media(self, movie_id):
        return self._send_file(movies.path(movie_id))

    def _send_file(self, f):
        """Streams a file with Range support so the TV can seek."""
        if not f:
            return self._json({'error': 'not found'}, 404)
        size = f.stat().st_size
        start, end = 0, size - 1
        rng = self.headers.get('Range', '')
        m = re.match(r'bytes=(\d*)-(\d*)', rng)
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
            else:  # bytes=-N: the last N bytes
                start = max(0, size - int(m.group(2)))
            if start > end:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        else:
            self.send_response(200)
        self.send_header('Content-Type', movies.VIDEO.get(f.suffix.lower()) or MEDIA.get(f.suffix.lower(), 'application/octet-stream'))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        self.end_headers()
        if self.command == 'HEAD':
            return
        left = end - start + 1
        try:
            with open(f, 'rb') as fh:
                fh.seek(start)
                while left > 0:
                    chunk = fh.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the TV seeked or stopped; it'll ask for a new range

    def do_HEAD(self):
        u = urlparse(self.path)
        if u.path.startswith('/station/kit/'):
            from urllib.parse import unquote
            return self._send_file(station.kit_path(unquote(u.path[len('/station/kit/'):])))
        if u.path == '/media':
            return self._media(parse_qs(u.query).get('id', [''])[0])
        return super().do_HEAD()

    def do_GET(self):
        global _tv_seen
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        p = u.path
        if p in ('/', '/tv'):
            self.path = '/index.html'
        elif p in ('/nag', '/dig', '/window', '/movies', '/station', '/remote', '/connect'):
            self.path = p + '.html'
        elif p == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        elif p == '/api/poll':
            with _lock:
                cmds = _queue[:]
                _queue.clear()
                _tv_seen = time.time()
            return self._json({'cmds': cmds, 'now': time.time()})
        elif p == '/api/state':
            return self._json({'tv': _tv_state, 'tv_online': time.time() - _tv_seen < 5,
                               'disk_free_gb': round(shutil.disk_usage(Path.home()).free / 1e9, 1),
                               'practice': practice_summary(), 'saves': _jsonl('dig_saves.jsonl')[-12:][::-1]})
        elif p == '/api/ready':  # the films kept on the Mac
            return self._json(ready.status())
        elif p == '/api/city':
            return self._json(sources.city_payload(q.get('id') or sources.DAY_CITY[datetime.now().weekday()]))
        elif p == '/api/cities':
            return self._json({'cities': [{'id': c['id'], 'name': c['name']} for c in sources.CITIES],
                               'today': sources.DAY_CITY[datetime.now().weekday()]})
        elif p == '/api/dig/next':
            # The TV says what it just left and why; that's the learning signal.
            if q.get('prev'):
                dig.feedback(q['prev'], int(float(q.get('watched') or 0)), q.get('reason', 'auto'))
            clip = dig.pick(q.get('lane') or None, q.get('last_lane') or None)
            return self._json(clip or {'error': 'pool empty'})
        elif p == '/api/dig/lanes':
            return self._json({'lanes': [l['name'] for l in dig.lanes() if l['clips']], 'detail': dig.lanes()})
        elif p == '/api/dig/stats':
            return self._json(dig.stats())
        elif p == '/api/practice':
            return self._json(practice_summary())
        elif p == '/api/movies/progress':  # how far iCloud has got bringing down a film you picked
            mid = q.get('id', '')
            size = station._cloud_size({'id': mid})
            pct = station.icloud_progress(Path.home() / mid)
            return self._json({'pct': pct, 'gb': round(size / 1e9, 1) if size else None, 'on_power': station.on_power()})
        elif p == '/api/movies':
            r = movies.scan()
            r['movies'] = [dict(m, poster=art.for_movie(m)) for m in r['movies']]
            return self._json(r)
        elif p.startswith('/poster/'):
            return self._send_file(art.path(p[len('/poster/'):]))
        elif p == '/api/subs':
            import subs
            return self._json(subs.get(q.get('id', '')))
        elif p == '/media':
            return self._media(q.get('id', ''))
        elif p == '/api/station/fetch':
            return self._json(station.fetch_status())
        elif p == '/api/convert':
            return self._json(convert.status())
        elif p == '/api/home':
            return self._json(home_summary())
        elif p == '/api/station/library':
            return self._json(station.library())
        elif p == '/api/station/now':
            return self._json(station.now())
        elif p == '/api/station/yourday':
            return self._json(personal.your_day())
        elif p == '/api/station/sports':
            import sports
            return self._json(sports.desk(q.get('desk', 'world')) or {'points': []})
        elif p.startswith('/station/kit/'):
            from urllib.parse import unquote
            return self._send_file(station.kit_path(unquote(p[len('/station/kit/'):])))
        elif p == '/station/track':
            return self._send_file(station.track_path(q.get('f', '')))
        elif p == '/station/beat':
            return self._send_file(station.beat_path(q.get('f', '')))
        elif p == '/station/recording':
            rec = settings.get('station_recording')
            return self._send_file(Path(rec).expanduser() if rec and Path(rec).expanduser().is_file() else None)
        elif p == '/api/remote':
            import tv
            return self._json({'url': f'http://{tv.mac_ip()}:{PORT}/remote', 'tv': f'http://{tv.mac_ip()}:{PORT}/'})
        elif p == '/api/remote-qr.svg':
            import tv
            body = qr_svg(f'http://{tv.mac_ip()}:{PORT}/remote').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'image/svg+xml')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def do_POST(self):
        p = urlparse(self.path).path
        body = self._body()
        if p == '/api/cmd':  # from the phone
            if body.get('do') == 'save':
                row = save_dig_moment(body.get('note', ''))
                with _lock:
                    _queue.append({'do': 'saved', 'ok': bool(row)})  # TV shows the toast
                return self._json({'ok': bool(row), 'saved': row})
            with _lock:
                _queue.append(body)
            return self._json({'ok': True})
        if p == '/api/dig/save':  # from the TV's own OK button
            row = save_dig_moment(body.get('note', ''))
            return self._json({'ok': bool(row), 'saved': row})
        if p == '/api/tvctl':  # phone asks the Mac to wake the TV and open a channel
            import tv
            ch = body.get('channel', '')
            if time.time() - _tv_seen < 5:  # a Room page is up: tell it to switch, so no old page stays in front
                with _lock:
                    _queue.append({'go': '/' + ch})
                return self._json({'ok': True, 'was_on': True})
            try:
                up = tv.bring_up(f'http://{tv.mac_ip()}:{PORT}/{ch}', lambda: time.time() - _tv_seen < 5)
                return self._json({'ok': up, 'was_on': False, 'error': '' if up else 'the TV did not open the page'})
            except Exception as e:
                return self._json({'ok': False, 'error': str(e)}, 500)
        if p == '/api/tv':  # TV heartbeat with what it's showing
            with _lock:
                _tv_state.clear()
                _tv_state.update(body)
            return self._json({'ok': True})
        if p == '/api/practice/log':
            row = {'date': datetime.now().date().isoformat(), 'at': datetime.now().isoformat(timespec='seconds'),
                   'minutes': int(body.get('minutes', 0)), 'set': body.get('set', '')}
            _jsonl_append('practice.jsonl', row)
            return self._json(practice_summary())
        if p == '/api/subs':  # subtitles on or off for a film; the first time on, they're found
            import subs
            return self._json(subs.toggle(body.get('id', ''), body.get('on')))
        if p == '/api/station/dur':
            station.actual_duration(body.get('uid'), body.get('dur'))
            return self._json({'ok': True})
        if p == '/api/station/play':  # from the phone: put a segment on now, and have the TV retune
            r = station.play_now(body.get('kind', ''), body.get('ref'))
            if r:
                with _lock:
                    _queue.append({'do': 'retune'})
            return self._json(r or {'ok': False})
        if p == '/api/station/blocked':  # the TV's YouTube player refused this video
            if body.get('id'):
                station.block(body['id'])
            return self._json({'ok': True})
        if p == '/api/station/star':  # from the phone: you love the music video that's on
            return self._json(station.mv_star())
        if p == '/api/station/skip':
            return self._json(station.skip())
        if p == '/api/movies/pos':  # the TV reports where you are
            if body.get('id') and body.get('duration'):
                movies.remember(body['id'], body.get('t', 0), body['duration'])
            return self._json({'ok': True})
        if p == '/api/ready':  # from the phone: keep a film ready, or stop
            ready.pick(body.get('id', ''), bool(body.get('keep', True)))
            return self._json(ready.status())
        if p == '/api/movies/fetch':  # download an iCloud placeholder
            return self._json({'ok': movies.fetch(body.get('id', ''))})
        if p == '/api/dig/bad':  # embed refused; never offer it again
            if body.get('id'):
                dig.feedback(body['id'], 0, 'error')
            return self._json({'ok': True})
        self._json({'error': 'not found'}, 404)


def serve(port=PORT, warm=True):
    log = lambda m: print(m, flush=True)  # noqa: E731
    if not dig.STORE.exists():  # first run after the upgrade: keep night one's clips
        old = sources._read().get('dig_pool', {}).get('v', [])
        log(f'  dig: migrated {dig.migrate(old)} clips')
    if warm:
        threading.Thread(target=sources.warm, kwargs={'log': log}, daemon=True).start()
    dig.keep_fresh(log)
    convert.start(log)  # only when convert_videos is on
    station.warm_beats(log)
    station.keep_shelf(log)
    station.start_fetcher()
    import funk
    funk.start([r['artist'] for r in station.crates()], log)
    art.start(log)
    ready.start(log)
    httpd = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'Room serving on :{port}', flush=True)
    httpd.serve_forever()
