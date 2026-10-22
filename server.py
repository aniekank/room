"""Room's local server: serves the TV channels, the phone remote, and a tiny command bus.

The TV page polls /api/poll every second; the phone remote POSTs /api/cmd. That keeps
the TV side to plain fetch() so the 2018-19 Tizen browser can run it.
"""
import json
import threading
import time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import dig
import sources
from paths import DATA

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
PORT = 8788

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


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    def log_message(self, fmt, *args):
        line = str(args[0]) if args else ''
        if '/api/poll' not in line and '/api/tv ' not in line and '/api/state' not in line:
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

    def do_GET(self):
        global _tv_seen
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        p = u.path
        if p in ('/', '/tv'):
            self.path = '/index.html'
        elif p in ('/nag', '/dig', '/window', '/remote'):
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
                               'practice': practice_summary(), 'saves': _jsonl('dig_saves.jsonl')[-12:][::-1]})
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
            try:
                on = tv.ensure_on()
                tv.open_url(f'http://{tv.mac_ip()}:{PORT}/{ch}')
                return self._json({'ok': True, 'was_on': on})
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
    httpd = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'Room serving on :{port}', flush=True)
    httpd.serve_forever()
