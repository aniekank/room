"""Dig Tube's engine: a wide, deep, self-refreshing pool that learns from Save and Skip.

- ~30 lanes, each a set of searches that walk years and artists, 30 results deep.
- Obscure clips are favored; mega-hits are rationed.
- Nothing you've watched comes back for three weeks; quick skips never come back.
- Lanes you save from get played more, lanes you skip get played less.
- Every night the stalest searches re-run, so new clips keep arriving.
"""
import json
import math
import random
import threading
import time
from pathlib import Path

import settings
from paths import DATA

STORE = DATA / 'dig.json'
_lock = threading.Lock()


def _years(tpl, a, b, step=1):
    return [tpl.format(y=y) for y in range(a, b + 1, step)]


BUILTIN_LANES = {
    'Soul Train 70s': _years('Soul Train {y} performance', 1971, 1979),
    'Soul Train 80s': _years('Soul Train {y} live', 1980, 1988),
    'R&B on TV 80s-90s': ['Showtime at the Apollo R&B performance 1988', 'Apollo 1990s R&B live performance', 'Arsenio Hall show R&B performance 1990',
                          'Arsenio Hall show R&B performance 1992', 'Soul Train 1993 R&B performance', 'BET Video Soul live performance', 'new jack swing live TV 1989'],
    'Quiet storm': ['quiet storm 1980s live performance', 'Anita Baker live 1986', 'Luther Vandross live 1980s TV', 'Sade live 1984 TV',
                    'Freddie Jackson live 1986', 'Peabo Bryson live 1980s'],
    'Neo-soul era': ['Soulquarians live', "D'Angelo live 2000", 'Erykah Badu live 1997', 'Jill Scott live 2001', 'Musiq Soulchild live TV 2001',
                     'Bilal live 2001', 'Maxwell live 1996 TV'],
    'Go-go (DC)': ['go-go band live DC 1980s', 'Rare Essence live 1980s', 'Chuck Brown live 1980s', 'Experience Unlimited EU live 1980s',
                   'Junkyard Band live 1980s', 'Trouble Funk live 1980s', 'go-go DC 1990s live crank'],
    'Chicago house': ['Chicago house 1980s club footage', 'Frankie Knuckles live', 'Larry Heard live performance', 'Ron Hardy Music Box',
                      'Bit Box Chicago house dancers 1980s', 'Chicago jack dancing 1980s', 'Marshall Jefferson live'],
    'Detroit techno & house': ['Detroit techno 1990s live', 'Moodymann live', 'Theo Parrish live set', 'Underground Resistance live',
                               'Derrick May live 1990s', 'Carl Craig live 1990s', 'Kenny Dixon Jr live'],
    'NYC & NJ deep house': ['Paradise Garage footage', 'Masters at Work live', 'Kerri Chandler live', 'Body and Soul NYC party footage',
                            'Larry Levan live', 'Joe Claussell live', 'Louie Vega live'],
    'UK soul & acid jazz': ['Incognito live 1990s', 'Brand New Heavies live TV', 'Soul II Soul live 1989', 'Young Disciples live',
                            'Jamiroquai 1993 live TV', 'acid jazz 1990s TV performance', 'Galliano live 1992'],
    'Top of the Pops soul': _years('Top of the Pops {y} soul', 1974, 1986, 2),
    'Disco & boogie TV': _years('Midnight Special {y} performance', 1973, 1980) + ['boogie funk 1980s TV performance', 'Solid Gold 1980s soul performance'],
    'Afrobeat': ['Fela Kuti Africa 70 live', 'Tony Allen live 1970s', 'Afrobeat 1970s Nigerian TV', 'Orlando Julius live',
                 'Ebo Taylor live', 'Fela Egypt 80 live 1980s'],
    'Highlife': ['Nigerian highlife 1970s performance', 'Ghana highlife 1970s TV', 'Ghana highlife 1980s TV', 'Osita Osadebe live',
                 'Oriental Brothers live', 'Victor Uwaifo live TV', 'palm wine music live'],
    'Juju & fuji': ['King Sunny Ade live 1980s', 'Ebenezer Obey live', 'juju music live 1980s', 'fuji music 1980s live', 'Sikiru Ayinde Barrister live'],
    'Nigerian boogie & disco': ['Nigerian boogie 1980s TV', 'Christy Essien live', 'Onyeka Onwenu 1980s', 'Nigerian disco 1980s performance',
                                'William Onyeabor', 'Nigerian TV 1980s music show'],
    'Ethio-jazz': ['Ethiopian jazz 1970s live', 'Mulatu Astatke live performance', 'Ethiopian 1970s TV music', 'Mahmoud Ahmed live 1970s',
                   'Alemayehu Eshete live', 'Tlahoun Gessesse live'],
    'South Africa': ['mbaqanga 1970s live', 'Mahlathini and the Mahotella Queens live', 'South African bubblegum 1980s TV', 'Brenda Fassie live 1980s',
                     'kwaito 1990s TV', 'South African jazz 1970s live', 'Hugh Masekela live 1980s'],
    'Congo & East Africa': ['Congolese rumba 1970s live TV', 'Franco TPOK Jazz live', 'Tabu Ley Rochereau live', 'Kenyan benga 1970s',
                            'soukous 1980s live', 'Zaiko Langa Langa live 1980s'],
    'West Africa (Mali, Senegal, Guinea)': ['Bembeya Jazz live', 'Orchestra Baobab live', 'Salif Keita live 1980s', 'Youssou N Dour live 1980s',
                                            'mbalax 1980s live', 'Ali Farka Toure live'],
    'Cape Verde & Angola': ['Cesaria Evora live 1990s', 'Cape Verde funana 1980s', 'Angolan semba live 1970s', 'Bonga live 1970s', 'coladeira live'],
    'Caribbean': ['soca 1980s live TV', 'zouk Kassav live 1980s', 'calypso 1970s TV performance', 'Haitian kompa live 1980s', 'steelpan band live 1970s'],
    'Jamaica': ['reggae live 1970s TV', 'dub sound system 1980s footage', 'rocksteady live TV', 'lovers rock 1980s live', 'Jamaican TV 1970s music',
                'King Tubby dub', 'Studio One live'],
    'Brazil 70s': ['MPB 1970s TV performance', 'Jorge Ben live 1970s', 'Brazilian samba funk 1970s live', 'Tim Maia live 1970s',
                   'Gal Costa live TV 1970s', 'Milton Nascimento live 1970s', 'Azymuth live'],
    'Latin': ['salsa 1970s live Fania', 'boogaloo live 1960s TV', 'cumbia 1970s TV performance', 'Puerto Rican salsa TV 1980s',
              'Hector Lavoe live 1970s', 'latin jazz 1970s live TV'],
    'City pop': ['Japanese city pop live 1980s TV', 'Tatsuro Yamashita live 1980s', 'Mariya Takeuchi live TV', 'Japanese TV 1980s performance funk',
                 'Anri live 1980s', 'Junko Yagami live'],
    'Asia 70s': ['Korean 1970s psych live TV', 'Thai funk 1970s', 'Indonesian 1970s pop TV', 'Cambodian rock 1960s', 'Hong Kong 1980s TV performance'],
    'Bollywood funk': ['R.D. Burman 1970s song funk', 'Bollywood disco 1980s song', 'Asha Bhosle 1970s cabaret song', 'Bappi Lahiri disco 1980s'],
    'Turkey & Middle East': ['Anatolian rock 1970s live', 'Selda Bagcan live', 'Googoosh live 1970s', 'Arabic funk 1970s', 'Erkin Koray live'],
    'Euro TV 60s-80s': ['French ye-ye 1960s TV', 'Italian TV 1970s funk performance', 'Serge Gainsbourg TV 1970s', 'Italo disco 1980s TV', 'Mina live 1970s TV'],
    'Library & soundtrack': ['1970s library music full album', 'Italian library music 1970s', '1970s TV theme funk', 'blaxploitation soundtrack',
                             'Piero Umiliani', 'French TV jazz funk 1970s'],
    'Scores & strings': ['film score recording session orchestra', 'Quincy Jones live orchestra 1970s', 'Ennio Morricone live', 'string section recording session 1970s soul',
                         'Charles Stepney arrangement', 'Barry White Love Unlimited Orchestra live'],
    '80s synth pop': ['Tears for Fears live 1985', 'Tears for Fears live TV 1983', 'Talk Talk live 1986', 'Depeche Mode live 1980s TV',
                      'Prefab Sprout live 1985', 'ABC live 1982 TV', 'Spandau Ballet live 1983', 'OMD live 1980s TV', 'Japan band live 1982',
                      'Scritti Politti live 1985', 'New Order live 1980s', 'Top of the Pops 1984 synth pop', 'Duran Duran live 1983 TV',
                      'Eurythmics live 1983 TV', 'Thomas Dolby live 1980s', 'synth pop 1980s TV performance'],
    'Jazz-prog & Canterbury': ['Soft Machine live 1970s', 'Caravan live 1970s', 'Hatfield and the North live', 'National Health live',
                               'Gilgamesh band live', 'Gentle Giant live 1970s', 'King Crimson live 1973', 'Frank Zappa live 1974',
                               'Brand X live 1970s', 'Gong live 1970s', 'Magma live 1970s', 'Camel live 1970s', 'Canterbury scene 1970s TV',
                               'Henry Cow live', 'Colosseum live 1971', 'Nucleus Ian Carr live', 'If band live 1970s', 'Egg band live',
                               'Isotope band live 1970s', 'Jade Warrior live'],
    'Prog: symphonic & art rock': ['Yes live 1972', 'Genesis live 1973', 'Emerson Lake and Palmer live 1970s', 'Renaissance live 1970s',
                                   'Procol Harum live 1970s', 'Alan Parsons Project', 'Roxy Music live 1973', 'Pink Floyd live 1972',
                                   'Van der Graaf Generator live', 'Jethro Tull live 1970s', 'Supertramp live 1970s', 'Barclay James Harvest live 1970s'],
    'Italian & Euro prog': ['PFM Premiata Forneria Marconi live 1970s', 'Banco del Mutuo Soccorso live', 'Le Orme live 1970s', 'Area band live 1970s Demetrio Stratos',
                            'Goblin live', 'Focus live 1973', 'Supersister live', 'Triana live 1970s', 'Ange live 1970s', 'Il Balletto di Bronzo',
                            'Arti e Mestieri live', 'Ekseption live'],
    'Krautrock': ['Can live 1970s', 'Neu! band', 'Harmonia band 1970s', 'Kraftwerk TV 1970s', 'Embryo band live 1970s', 'Amon Duul II live',
                  'Popol Vuh', 'Agitation Free live', 'Guru Guru live 1970s', 'Tangerine Dream live 1970s'],
    'Prog beyond Europe': ['O Terço live 1970s', 'Som Nosso de Cada Dia', 'Mutantes live 1970s', 'Far East Family Band', 'Japanese progressive rock 1970s live',
                           'Spinetta Invisible live', 'Los Jaivas live 1970s', 'Aphrodite\'s Child live', 'Hungarian prog rock 1970s TV', 'Polish jazz rock 1970s TV'],
    'Fusion on TV': ['Mahavishnu Orchestra live', 'Return to Forever live 1970s', 'Weather Report live 1978', 'Jean-Luc Ponty live 1970s',
                     'Allan Holdsworth live', 'Pat Metheny Group live 1980s', 'Jaco Pastorius live', 'jazz fusion 1970s TV performance',
                     'Billy Cobham live 1970s', 'Stanley Clarke live 1970s'],
    'Soft rock & MOR': ['soft rock 1970s TV performance', 'yacht rock live TV 1979', 'Bread live 1970s', 'Michael McDonald live 1980',
                        'Carpenters live TV', 'Steely Dan live 1970s'],
    'Gospel TV': ['gospel choir 1970s TV performance', 'Edwin Hawkins Singers live', 'Andrae Crouch live 1970s', 'Bobby Jones Gospel 1980s',
                  'Walter Hawkins live', 'Clark Sisters live 1980s'],
    'Jazz on TV': ['jazz quartet 1960s TV performance', 'Ahmad Jamal live 1960s', 'Roy Ayers live 1970s', 'Jazz Casual Ralph Gleason',
                   'Herbie Hancock live 1970s TV', 'Lonnie Liston Smith live', 'spiritual jazz live 1970s'],
    'Hip-hop TV 80s-90s': ['Yo MTV Raps live 1990', 'Video Music Box 1980s', 'Rap City freestyle 1990s', 'Soul Train 1990s hip hop performance',
                           'Graffiti Rock 1984', 'Showtime at the Apollo rap 1990'],
}


def _lanes():
    s = settings.load()
    picked = {k: v for k, v in BUILTIN_LANES.items() if not s['dig_lanes'] or k in s['dig_lanes']}
    picked.update(s['extra_lanes'])
    return picked


LANES = _lanes()

SKIP_WORDS = ('reaction', 'tutorial', 'lesson', 'how to', 'how i', 'interview', 'thoughts on', 'podcast', 'review', 'shorts',
              'cover', 'karaoke', 'tribute', 'type beat', 'remix', 'explained', 'breakdown', 'sample', 'reacts', 'ai ',
              'livestream', 'live stream', '24/7', 'documentary', 'top 10', 'top 20', 'top 50', 'ranking', 'full movie', 'trailer',
              'lyrics', 'lyric video', 'slowed', 'reverb', '8d audio', 'nightcore', 'sped up')

FRESH_DAYS = 21          # don't replay a clip for three weeks
QUICK_SKIP = 45          # seconds: skipping before this means "not for me"
MEGA_VIEWS = 3_000_000   # rationed: these are the clips everyone already knows
NIGHTLY = 45             # searches re-run each night

# ---------------------------------------------------------------- store


def _blank():
    return {'clips': {}, 'queries': {}, 'plays': {}, 'banned': {}, 'saves': {}, 'lane_stats': {}, 'last_refresh': 0}


def load():
    try:
        return json.loads(STORE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return _blank()


def save(db):
    tmp = STORE.with_suffix('.tmp')
    tmp.write_text(json.dumps(db, separators=(',', ':')))
    tmp.replace(STORE)


def _stat(db, lane):
    return db['lane_stats'].setdefault(lane, {'plays': 0, 'saves': 0, 'skips': 0})

# ---------------------------------------------------------------- search


def _search(q, n=30):
    import yt_dlp
    with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'skip_download': True, 'noprogress': True}) as ydl:
        res = ydl.extract_info(f'ytsearch{n}:{q}', download=False)
    return res.get('entries') or []


def _keep(e):
    t = (e.get('title') or '').lower()
    d = e.get('duration') or 0
    return (e.get('id') and e.get('live_status') not in ('is_live', 'is_upcoming')
            and 90 <= d <= 2 * 3600 and not any(w in t for w in SKIP_WORDS))


def run_query(lane, q):
    hits = _search(q)
    now = time.time()
    with _lock:
        db = load()
        added = 0
        for e in hits:
            if not _keep(e) or e['id'] in db['banned']:
                continue
            if e['id'] not in db['clips']:
                added += 1
                db['clips'][e['id']] = {'id': e['id'], 'title': e['title'], 'lane': lane, 'duration': e.get('duration') or 0,
                                        'views': e.get('view_count') or 0, 'added': now}
        db['queries'][q] = now
        save(db)
    return added


def all_queries():
    return [(lane, q) for lane, qs in LANES.items() for q in qs]


def refresh(limit=None, log=print):
    """Run never-run searches first, then the stalest ones."""
    db = load()
    todo = sorted(all_queries(), key=lambda lq: db['queries'].get(lq[1], 0))
    if limit:
        todo = todo[:limit]
    total = 0
    for i, (lane, q) in enumerate(todo):
        try:
            n = run_query(lane, q)
            total += n
        except Exception as e:
            log(f'  dig search failed ({q}): {e}')
            continue
        if i % 20 == 19:
            log(f'  dig refresh {i + 1}/{len(todo)}: +{total} clips')
    with _lock:
        db = load()
        db['last_refresh'] = time.time()
        save(db)
    log(f'  dig refresh done: +{total} new clips, {len(load()["clips"])} total')
    return total


def keep_fresh(log=print):
    """Background loop for the server: fill the never-run searches, then a nightly top-up."""
    def loop():
        while True:
            db = load()
            never = [q for _, q in all_queries() if q not in db['queries']]
            try:
                if never:
                    refresh(len(never), log)
                elif time.time() - db.get('last_refresh', 0) > 20 * 3600 and time.localtime().tm_hour in (2, 3, 4, 5):
                    refresh(NIGHTLY, log)
            except Exception as e:
                log(f'  dig refresh error: {e}')
            time.sleep(1800)
    threading.Thread(target=loop, daemon=True).start()

# ---------------------------------------------------------------- picking


def lane_weight(st):
    w = (1 + 0.6 * st.get('saves', 0)) / (1 + 0.15 * st.get('skips', 0))
    return max(0.35, min(4.0, w))


def clip_weight(c):
    w = 1 / (math.log10(c.get('views', 0) + 10) ** 2)   # 1k views ~0.11, 1M ~0.028
    if c.get('views', 0) > MEGA_VIEWS:
        w *= 0.3
    return w


def pick(lane=None, last_lane=None):
    with _lock:
        db = load()
        now = time.time()
        fresh_cut = now - FRESH_DAYS * 86400
        clips = [c for c in db['clips'].values() if c['id'] not in db['banned']]
        if lane:
            clips = [c for c in clips if c['lane'] == lane]
        cand = [c for c in clips if db['plays'].get(c['id'], 0) < fresh_cut]
        if not cand:  # watched everything recently: oldest-played first
            cand = sorted(clips, key=lambda c: db['plays'].get(c['id'], 0))[:50]
        if not cand:
            return None
        if not lane:
            by_lane = {}
            for c in cand:
                by_lane.setdefault(c['lane'], []).append(c)
            lanes = [l for l in by_lane if l != last_lane] or list(by_lane)
            weights = [lane_weight(db['lane_stats'].get(l, {})) for l in lanes]
            cand = by_lane[random.choices(lanes, weights)[0]]
        c = random.choices(cand, [clip_weight(x) for x in cand])[0]
        db['plays'][c['id']] = now
        _stat(db, c['lane'])['plays'] += 1
        save(db)
        return c


def feedback(clip_id, watched, reason):
    """reason: 'skip' (you pressed next), 'end', 'auto' (dwell timer), 'error'."""
    with _lock:
        db = load()
        c = db['clips'].get(clip_id)
        if not c:
            return
        if reason == 'error' or (reason == 'skip' and watched < QUICK_SKIP):
            db['banned'][clip_id] = time.time()
            if reason == 'skip':
                _stat(db, c['lane'])['skips'] += 1
        save(db)


def saved(clip_id):
    with _lock:
        db = load()
        c = db['clips'].get(clip_id)
        if c:
            db['saves'][clip_id] = time.time()
            _stat(db, c['lane'])['saves'] += 1
            save(db)


def lanes():
    db = load()
    counts = {}
    for c in db['clips'].values():
        if c['id'] not in db['banned']:
            counts[c['lane']] = counts.get(c['lane'], 0) + 1
    return [{'name': l, 'clips': counts.get(l, 0)} for l in LANES]


def stats():
    db = load()
    now = time.time()
    return {'clips': len(db['clips']), 'banned': len(db['banned']), 'searches_run': len(db['queries']),
            'searches_total': len(all_queries()), 'played_3wk': sum(1 for t in db['plays'].values() if t > now - FRESH_DAYS * 86400),
            'lanes': {l: dict(s, weight=round(lane_weight(s), 2)) for l, s in db['lane_stats'].items()}}


OLD_LANES = {'Soul Train': 'Soul Train 70s', 'Afrobeat & highlife TV': 'Highlife', 'Chicago house history': 'Chicago house'}


def migrate(old_pool):
    """Carry the first night's clips over so nothing's lost while the big build runs."""
    with _lock:
        db = load()
        for e in old_pool:
            lane = OLD_LANES.get(e['lane'], e['lane'])
            if lane in LANES and e['id'] not in db['clips'] and not any(w in e['title'].lower() for w in SKIP_WORDS):
                db['clips'][e['id']] = {'id': e['id'], 'title': e['title'], 'lane': lane, 'duration': e.get('duration', 0),
                                        'views': e.get('views', 0), 'added': time.time()}
        save(db)
        return len(db['clips'])
