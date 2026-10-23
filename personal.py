"""Your Day: what the station's rundown segment knows about you, from the Mac and your accounts.

  calendar + reminders   macOS Calendar and Reminders via EventKit (scripts/eventkit.js; macOS asks once)
  notion                 tasks from a database and a study card from your notes, with your own integration key
                         (settings: notion_token, notion_tasks, notion_notes)
  files                  what you touched lately in iCloud Drive and on the Desktop
  room                   Keys streak, Dig Tube saves, today's World Window city and weather

Every source is optional and cached; one failing never blanks the segment.
"""
import json
import os
import random
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import settings
import sources
from paths import DATA

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
EVENTKIT = ROOT / 'scripts' / 'eventkit.js'
HOME = Path.home()
ICLOUD = HOME / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'


def _cached(key, max_age, fn, fallback):
    try:
        return sources.cached('you:' + key, max_age, fn)
    except Exception:
        return fallback


def calendar():
    def build():
        r = subprocess.run(['osascript', '-l', 'JavaScript', str(EVENTKIT), '1'], capture_output=True, text=True, timeout=30)
        d = json.loads(r.stdout or '{}')
        now = time.time()
        ev = sorted((e for e in d.get('events', []) if e['allDay'] or e['end'] > now), key=lambda e: (not e['allDay'], e['start']))
        return {'events': ev[:8], 'reminders': d.get('reminders', [])[:8], 'errors': d.get('errors', [])}
    return _cached('calendar', 600, build, {'events': [], 'reminders': [], 'errors': ['calendar unavailable']})


# ---------------------------------------------------------------- notion

def _notion(path, body=None):
    tok = settings.get('notion_token')
    req = urllib.request.Request('https://api.notion.com/v1/' + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': f'Bearer {tok}', 'Notion-Version': '2022-06-28',
                                          'Content-Type': 'application/json'}, method='POST' if body is not None else 'GET')
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def _plain(rich):
    return ''.join(t.get('plain_text', '') for t in rich or [])


def notion_tasks():
    """Open tasks from your tasks database, soonest due first."""
    db = settings.get('notion_tasks')
    if not (settings.get('notion_token') and db):
        return []

    def build():
        rows = _notion(f'databases/{db}/query', {'page_size': 50}).get('results', [])
        out = []
        for row in rows:
            title, status, due = '', '', None
            for p in row.get('properties', {}).values():
                t = p.get('type')
                if t == 'title':
                    title = _plain(p['title'])
                elif t == 'status' and p.get('status'):
                    status = p['status'].get('name', '')
                elif t == 'checkbox' and p.get('checkbox'):
                    status = 'Done'
                elif t == 'date' and p.get('date') and not due:
                    due = p['date'].get('start')
            if title and status.lower() not in ('done', 'complete', 'completed', 'archived'):
                out.append({'title': title, 'status': status, 'due': due})
        out.sort(key=lambda x: (x['due'] is None, x['due'] or ''))
        return out[:8]
    return _cached('notion_tasks', 900, build, [])


def notion_card():
    """One line worth remembering from your notes pages: a bullet, a to-do or a short paragraph."""
    pages = settings.get('notion_notes') or []
    if not (settings.get('notion_token') and pages):
        return None

    def build():
        lines = []
        for pid in pages:
            page = _notion(f'pages/{pid}')
            name = ''.join(_plain(p.get('title')) for p in page.get('properties', {}).values() if p.get('type') == 'title')
            for b in _notion(f'blocks/{pid}/children?page_size=100').get('results', []):
                kind = b.get('type')
                text = _plain(b.get(kind, {}).get('rich_text')) if isinstance(b.get(kind), dict) else ''
                if 30 <= len(text) <= 260 and kind in ('paragraph', 'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'to_do'):
                    lines.append({'page': name, 'text': text})
        return lines
    lines = _cached('notion_notes', 6 * 3600, build, [])
    if not lines:
        return None
    return random.Random(datetime.now().strftime('%Y-%m-%d %H')).choice(lines)  # a new card each hour


# ---------------------------------------------------------------- files

KINDS = {'.pdf': 'PDF', '.md': 'Notes', '.docx': 'Doc', '.doc': 'Doc', '.pages': 'Doc', '.key': 'Deck', '.pptx': 'Deck',
         '.xlsx': 'Sheet', '.numbers': 'Sheet', '.csv': 'Data', '.png': 'Image', '.jpg': 'Image', '.mp3': 'Audio',
         '.wav': 'Audio', '.html': 'Page', '.py': 'Code', '.ipynb': 'Notebook'}


def recent_files(days=3, n=6):
    """What you've been working on: the newest documents, top two levels of iCloud Drive and the Desktop."""
    def build():
        cutoff, found = time.time() - days * 86400, []
        for base, label in ((ICLOUD, 'iCloud Drive'), (HOME / 'Desktop', 'Desktop')):
            try:
                for dp, dns, fns in os.walk(base):
                    depth = len(Path(dp).relative_to(base).parts)
                    dns[:] = [d for d in dns if not d.startswith('.') and depth < 2 and d not in ('Projects', 'node_modules')]
                    for f in fns:
                        ext = os.path.splitext(f)[1].lower()
                        if f.startswith('.') or ext not in KINDS:
                            continue
                        try:
                            m = os.stat(os.path.join(dp, f)).st_mtime
                        except OSError:
                            continue
                        if m >= cutoff:
                            where = label if depth == 0 else f'{label} › {Path(dp).name}'
                            found.append({'name': Path(f).stem, 'kind': KINDS[ext], 'where': where, 't': m})
            except (PermissionError, OSError):
                continue  # the Desktop needs a privacy grant when Room runs in the background
        found.sort(key=lambda x: -x['t'])
        return found[:n]
    return _cached('files', 1800, build, [])


# ---------------------------------------------------------------- room's own

def room_bits():
    import server
    out = {'practice': server.practice_summary(), 'saves': server._jsonl('dig_saves.jsonl')[-3:][::-1]}
    try:
        city = next(c for c in sources.CITIES if c['id'] == sources.DAY_CITY[datetime.now().weekday()])
        out['city'] = {'name': city['name'], 'tz': city['tz'], 'weather': sources.weather(city)}
    except Exception:
        out['city'] = None
    return out


def your_day():
    cal = calendar()
    return {'at': time.time(), 'events': cal['events'], 'reminders': cal['reminders'], 'tasks': notion_tasks(),
            'card': notion_card(), 'files': recent_files(), **room_bits(),
            'notes': [e for e in cal.get('errors', [])] + ([] if settings.get('notion_token') else ['notion: add notion_token to settings'])}

