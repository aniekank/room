"""Where World Window gets its material: radio streams, city views, weather.

Everything external is cached in data/cache.json so the TV never waits on a search,
and a dead source falls through to the next one instead of a blank screen.
"""
import json
import threading
import time
import urllib.parse
import urllib.request

import settings
from paths import DATA

CACHE = DATA / 'cache.json'
_lock = threading.Lock()
UA = {'User-Agent': 'Room/1.0 (personal TV channels)'}

# ---------------------------------------------------------------- cities

BUILTIN_CITIES = [
    {'id': 'chicago', 'name': 'Chicago', 'tz': 'America/Chicago', 'lat': 41.88, 'lon': -87.63,
     'lens': 'Where house got its name: the Warehouse, Frankie Knuckles, Ron Hardy at the Music Box, Larry Heard turning drum machines into feelings.',
     'stations': [{'name': 'WHPK', 'q': {'name': 'WHPK'}, 'note': 'UChicago college radio, house and hip-hop shows'},
                  {'name': 'WDCB Jazz & Blues', 'q': {'name': 'WDCB'}},
                  {'name': 'Deeper Shades Of House', 'q': {'name': 'Deeper Shades Of House'}}],
     'views': ['Chicago live cam', 'Chicago EarthCam live', 'Chicago 4K walking tour']},
    {'id': 'lagos', 'name': 'Lagos', 'tz': 'Africa/Lagos', 'lat': 6.52, 'lon': 3.38,
     'lens': "Afrobeat's birthplace (Fela's Shrine) and Afrobeats' engine room: the city that sets the continent's tempo.",
     'stations': [{'name': 'Cool FM 96.9', 'q': {'name': 'Cool FM', 'countrycode': 'NG'}},
                  {'name': 'Wazobia FM', 'q': {'name': 'Wazobia FM: Lagos'}},
                  {'name': 'LagosJump Radio', 'q': {'name': 'LagosJump Radio'}}],
     'views': ['Lagos live cam', 'Lagos 4K drive', 'Lagos walking tour 4K', 'Victoria Island Lagos drive 4K']},
    {'id': 'detroit', 'name': 'Detroit', 'tz': 'America/Detroit', 'lat': 42.33, 'lon': -83.05,
     'lens': "Motown, then techno, then Dilla's MPC. Moodymann and Theo Parrish keep house dusty and soulful here.",
     'stations': [{'name': 'WDET 101.9', 'q': {'name': 'WDET'}},
                  {'name': '313live', 'q': {'name': '313live.org'}},
                  {'name': 'WRCJ Classical & Jazz', 'q': {'name': 'WRCJ'}}],
     'views': ['Detroit live cam', 'Detroit 4K walking tour downtown']},
    {'id': 'london', 'name': 'London', 'tz': 'Europe/London', 'lat': 51.51, 'lon': -0.13,
     'lens': 'Pirate radio to Rinse and NTS: garage, grime, broken beat, afro-swing and UK funky all cross-pollinating.',
     'stations': [{'name': 'NTS 1', 'q': {'name': 'NTS Radio 1'}},
                  {'name': 'Rinse FM', 'q': {'name': 'Rinse UK'}},
                  {'name': 'NTS 2', 'q': {'name': 'NTS Radio 2'}}],
     'views': ['London live cam street', 'London webcam live Thames']},
    {'id': 'johannesburg', 'name': 'Johannesburg', 'tz': 'Africa/Johannesburg', 'lat': -26.20, 'lon': 28.05,
     'lens': "Kwaito, then deep house's second home (Black Coffee), then amapiano's log drums out of Pretoria and Soweto.",
     'stations': [{'name': 'Metro FM', 'q': {'name': 'Metro FM', 'countrycode': 'ZA'}},
                  {'name': 'Amapiano FM', 'q': {'name': 'Amapiano FM'}},
                  {'name': 'Jozi FM', 'q': {'name': 'Jozi FM'}}],
     'views': ['Johannesburg live cam', 'Soweto 4K walking tour', 'Johannesburg 4K drive']},
    {'id': 'accra', 'name': 'Accra', 'tz': 'Africa/Accra', 'lat': 5.60, 'lon': -0.19,
     'lens': 'Highlife and palm-wine guitar, then hiplife and azonto: the melodic cousin next door to Lagos.',
     'stations': [{'name': 'Joy FM', 'q': {'name': 'Joy Fm', 'countrycode': 'GH'}},
                  {'name': 'Hitz 103.9', 'q': {'name': 'Hitz 103.9'}},
                  {'name': 'Ghana Music Radio', 'q': {'name': 'Ghana Music Radio'}}],
     'views': ['Accra live cam', 'Accra Ghana 4K walking tour', 'Osu Accra walk 4K']},
]

# Day-of-week rotation (Mon=0) lined up with the practice week: house Monday,
# R&B Wednesday, Afro on the explorer days.
DEFAULT_DAY_CITY = ['chicago', 'lagos', 'detroit', 'london', 'johannesburg', 'accra', 'chicago']


def _cities():
    s = settings.load()
    by_id = {c['id']: c for c in BUILTIN_CITIES}
    picked = [by_id[i] for i in s['cities'] if i in by_id] if s['cities'] else list(BUILTIN_CITIES)
    picked += s['extra_cities']
    ids = [c['id'] for c in picked]
    day = s['day_city'] or (DEFAULT_DAY_CITY if ids == [c['id'] for c in BUILTIN_CITIES] else None)
    if not day or len(day) != 7 or any(d not in ids for d in day):
        day = [ids[i % len(ids)] for i in range(7)]
    return picked, day


CITIES, DAY_CITY = _cities()


def reload():
    """Pick up settings changes without a restart."""
    global CITIES, DAY_CITY
    CITIES, DAY_CITY = _cities()

# ---------------------------------------------------------------- cache


def _read():
    try:
        return json.loads(CACHE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(c):
    CACHE.parent.mkdir(exist_ok=True)
    tmp = CACHE.with_suffix('.tmp')
    tmp.write_text(json.dumps(c, indent=1))
    tmp.replace(CACHE)


def cached(key, max_age, fn):
    with _lock:
        c = _read()
        hit = c.get(key)
    if hit and time.time() - hit['t'] < max_age:
        return hit['v']
    try:
        v = fn()
    except Exception as e:  # network down: serve stale rather than nothing
        if hit:
            return hit['v']
        raise e
    with _lock:
        c = _read()
        c[key] = {'t': time.time(), 'v': v}
        _write(c)
    return v


def _get_json(url, timeout=15):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)

# ---------------------------------------------------------------- radio


def _radio_search(q):
    params = dict(q, hidebroken='true', order='clickcount', reverse='true', limit='10')
    for mirror in ('de1', 'nl1', 'at1'):
        try:
            rows = _get_json(f'https://{mirror}.api.radio-browser.info/json/stations/search?' + urllib.parse.urlencode(params))
            break
        except Exception:
            rows = []
    # The TV's browser plays MP3/AAC over plain <audio>; HLS (.m3u8) needs a newer engine.
    ok = [r for r in rows if r.get('lastcheckok') and r.get('codec', '').upper() in ('MP3', 'AAC', 'AAC+')
          and '.m3u8' not in r.get('url_resolved', '')]
    return [{'url': r['url_resolved'], 'codec': r['codec'], 'bitrate': r['bitrate'], 'homepage': r.get('homepage', '')} for r in ok[:3]]


def stations(city):
    out = []
    for s in city['stations']:
        found = cached('radio:' + s['name'], 86400, lambda s=s: _radio_search(s['q']))
        if found:
            out.append({'name': s['name'], 'note': s.get('note', ''), 'urls': [f['url'] for f in found]})
    return out

# ---------------------------------------------------------------- youtube


def _yt_search(query, n=12):
    import yt_dlp
    import engine
    with yt_dlp.YoutubeDL(engine.opts(extract_flat=True, skip_download=True)) as ydl:
        res = ydl.extract_info(f'ytsearch{n}:{query}', download=False)
    return [{'id': e['id'], 'title': e.get('title') or '', 'live': e.get('live_status') == 'is_live',
             'duration': e.get('duration') or 0, 'views': e.get('view_count') or 0,
             'channel': e.get('channel') or e.get('uploader') or '', 'verified': bool(e.get('channel_is_verified'))}
            for e in res.get('entries') or [] if e.get('id')]


def views(city):
    """Live street cams first, then long walking/drive footage (muted, random start)."""
    def build():
        picks, seen = [], set()
        name = city['name'].lower()
        for q in city['views']:
            for e in _yt_search(q, 10):
                if e['id'] in seen or name not in e['title'].lower():
                    continue
                if e['live'] or e['duration'] >= 600:
                    seen.add(e['id'])
                    picks.append(e)
        def score(e):
            t = e['title'].lower()
            s = 4 if e['live'] else 0
            s += 2 * any(w in t for w in ('walk', 'drive', 'cam', 'driving'))
            s += 1 * ('4k' in t)
            s -= 3 * any(w in t for w in ('crazy', 'vlog', 'reaction', 'why ', 'how ', 'becoming', 'wealthy', 'truth', 'shocking', '?'))
            return (-s, -e['views'])
        picks.sort(key=score)
        return picks[:8]
    return cached('views:' + city['id'], 6 * 3600, build)


def weather(city):
    def build():
        q = urllib.parse.urlencode({'latitude': city['lat'], 'longitude': city['lon'], 'timezone': city['tz'],
                                    'current': 'temperature_2m,weather_code,is_day',
                                    'temperature_unit': 'celsius' if unit == 'C' else 'fahrenheit'})
        cur = _get_json('https://api.open-meteo.com/v1/forecast?' + q)['current']
        return {'temp': round(cur['temperature_2m']), 'unit': unit, 'code': cur['weather_code'], 'day': bool(cur['is_day'])}
    unit = 'C' if str(settings.get('temp_unit')).upper().startswith('C') else 'F'
    return cached(f'wx:{city["id"]}:{unit}', 1800, build)


def city_payload(city_id):
    city = next((c for c in CITIES if c['id'] == city_id), CITIES[0])
    out = {k: city[k] for k in ('id', 'name', 'tz', 'lens')}
    for key, fn in (('stations', stations), ('views', views), ('weather', weather)):
        try:
            out[key] = fn(city)
        except Exception as e:
            out[key] = [] if key != 'weather' else None
            out.setdefault('errors', []).append(f'{key}: {e}')
    return out


def warm(log=print):
    """Fill the cache in the background so the first channel flip is instant."""
    for c in CITIES:
        try:
            city_payload(c['id'])
            log(f'  warmed {c["name"]}')
        except Exception as e:
            log(f'  {c["name"]}: {e}')
