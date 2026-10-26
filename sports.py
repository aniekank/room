"""FlyBoy Sports: a desk of what's happening, then the greats on tape.

Each segment opens on a desk: the NFL from NFL Intelligence, club football from Club Football Intelligence, the
World Cup from World Cup Intelligence (all three yours, at taskintel.app), the NBA, NHL and MLB scoreboards, and
headlines from tennis, boxing, rugby and cricket (ESPN's public feeds). Then two clips from the archive: the greats,
the revered, and the legends in the making, as music videos are, fetched onto the Mac ahead of airtime.

Who's followed comes first on every desk. Change it with "sports_follow" in settings.json, shaped like FOLLOW.
"""
import random
import threading
import urllib.parse
from datetime import datetime

import settings
import sources

NFLI = 'https://nfl.taskintel.app'
CFI = 'https://club.taskintel.app'
WCI = 'https://worldcup.taskintel.app'
ESPN = 'https://site.api.espn.com/apis/site/v2/sports'

FOLLOW = {  # the storied, and the ones building a story now
    'nfl': ['PIT', 'SF', 'DAL', 'GB', 'NE', 'KC', 'PHI', 'BAL', 'BUF', 'DET'],
    'club': ['Real Madrid', 'Barcelona', 'Manchester United', 'Liverpool', 'Arsenal', 'Manchester City',
             'Bayern Munich', 'Juventus', 'AC Milan', 'Inter'],
    'nba': ['LAL', 'BOS', 'GS', 'CHI', 'SA', 'OKC', 'DEN', 'NY'],
    'nhl': ['MTL', 'DET', 'EDM', 'TOR', 'PIT', 'COL'],
    'mlb': ['NYY', 'LAD', 'BOS', 'STL', 'SF', 'ATL'],
}
LEAGUES = ['epl', 'laliga', 'seriea', 'bundesliga', 'ucl']  # the club desk goes round these

DESKS = {  # name, where it comes from, what goes on tape after it
    'nfl': ('NFL Desk', 'NFL Intelligence · nfl.taskintel.app', ['American football']),
    'club': ('Club Football Desk', 'Club Football Intelligence · club.taskintel.app', ['Soccer']),
    'worldcup': ('World Cup Desk', 'World Cup Intelligence · worldcup.taskintel.app', ['World Cup']),
    'scoreboard': ('Scoreboard', 'NBA · NHL · MLB', ['Basketball', 'Hockey', 'Baseball']),
    'world': ('Around the World', 'Tennis · Boxing · Rugby · Cricket', ['Tennis', 'Boxing', 'Rugby', 'Cricket', 'Track & field']),
}
SEASON = {  # months each desk's sport is on (1-12); out of season it airs less
    'nfl': {9, 10, 11, 12, 1, 2},
    'club': {8, 9, 10, 11, 12, 1, 2, 3, 4, 5},
    'worldcup': {6, 7},
}

GREAT, REVERED, RISING = 'The greats', 'Revered', 'Legend in the making'
# (who, what to search for after the name, tier): one clip each, 1-25 minutes, as the TV's Mac-side player wants
CLIPS = {
    'Boxing': [
        ('Muhammad Ali', 'vs George Foreman Rumble in the Jungle 1974', GREAT),
        ('Muhammad Ali', 'vs Joe Frazier Thrilla in Manila highlights', GREAT),
        ('Sugar Ray Leonard', 'vs Marvin Hagler 1987 highlights', GREAT),
        ('Marvin Hagler', 'vs Thomas Hearns 1985 the war', GREAT),
        ('Mike Tyson', 'knockouts 1986 1988 prime', GREAT),
        ('Sugar Ray Robinson', 'greatest fights highlights', GREAT),
        ('Floyd Mayweather', 'defensive genius highlights', REVERED),
        ('Manny Pacquiao', 'prime highlights knockouts', REVERED),
        ('Roy Jones Jr', 'prime highlights', REVERED),
        ('Oleksandr Usyk', 'vs Tyson Fury undisputed highlights', REVERED),
        ('Terence Crawford', 'vs Errol Spence highlights', REVERED),
        ('Naoya Inoue', 'monster knockouts highlights', RISING),
        ('Shakur Stevenson', 'highlights', RISING),
        ('Jaron Boots Ennis', 'highlights', RISING),
    ],
    'Soccer': [
        ('Pele', 'Santos and Brazil goals', GREAT),
        ('Diego Maradona', 'Napoli magic highlights', GREAT),
        ('Johan Cruyff', 'Ajax Barcelona total football', GREAT),
        ('Zinedine Zidane', 'Real Madrid best moments', GREAT),
        ('Ronaldinho', 'Barcelona magic skills', GREAT),
        ('Thierry Henry', 'Arsenal invincibles goals', GREAT),
        ('Lionel Messi', 'Barcelona best goals', GREAT),
        ('Cristiano Ronaldo', 'Manchester United Real Madrid best goals', GREAT),
        ('Jay-Jay Okocha', 'skills and goals', REVERED),
        ('George Weah', 'AC Milan goals', REVERED),
        ('Didier Drogba', 'Chelsea big game goals', REVERED),
        ('Samuel Eto\'o', 'Barcelona Inter goals', REVERED),
        ('Kylian Mbappe', 'best goals', RISING),
        ('Erling Haaland', 'goals', RISING),
        ('Lamine Yamal', 'skills and goals', RISING),
        ('Jude Bellingham', 'Real Madrid goals', RISING),
        ('Jamal Musiala', 'dribbling and goals', RISING),
    ],
    'World Cup': [
        ('Brazil 1970', 'World Cup final Carlos Alberto goal Italy', GREAT),
        ('Maradona', 'Argentina England 1986 World Cup', GREAT),
        ('Roger Milla', 'Cameroon World Cup 1990', REVERED),
        ('Nigeria', 'World Cup 1994 Super Eagles highlights', REVERED),
        ('Ronaldo R9', 'World Cup 2002 Brazil goals', GREAT),
        ('Zidane', 'France Brazil 1998 World Cup final', GREAT),
        ('Ghana', 'World Cup 2010 Black Stars run', REVERED),
        ('Argentina France', '2022 World Cup final extended highlights', GREAT),
        ('Morocco', '2022 World Cup semi final run', REVERED),
        ('Spain', '2010 World Cup winning goal Iniesta', GREAT),
        ('Spain', 'World Cup 2026 highlights', RISING),
        ('Lamine Yamal', 'World Cup 2026', RISING),
    ],
    'American football': [
        ('Jerry Rice', 'NFL Films highlights', GREAT),
        ('Walter Payton', 'Sweetness highlights', GREAT),
        ('Barry Sanders', 'ankle breaking runs', GREAT),
        ('Lawrence Taylor', 'highlights NFL Films', GREAT),
        ('Joe Montana', 'Super Bowl drives', GREAT),
        ('Steel Curtain', 'Steelers 1970s NFL Films', GREAT),
        ('Tom Brady', 'Super Bowl comeback 28-3', GREAT),
        ('Deion Sanders', 'Prime Time highlights', REVERED),
        ('Randy Moss', 'rookie season highlights', REVERED),
        ('Michael Vick', 'Falcons highlights', REVERED),
        ('Patrick Mahomes', 'no look and magic plays', RISING),
        ('Lamar Jackson', 'best runs', RISING),
        ('Josh Allen', 'highlights', RISING),
        ('Jayden Daniels', 'highlights', RISING),
        ('Ja\'Marr Chase', 'highlights', RISING),
    ],
    'Basketball': [
        ('Michael Jordan', 'best plays 1988 1991', GREAT),
        ('Magic Johnson', 'Showtime Lakers highlights', GREAT),
        ('Larry Bird', 'Celtics best plays', GREAT),
        ('Kareem Abdul-Jabbar', 'skyhook highlights', GREAT),
        ('Dr J Julius Erving', 'ABA dunks highlights', GREAT),
        ('Kobe Bryant', '81 points game highlights', GREAT),
        ('Allen Iverson', 'crossovers highlights', REVERED),
        ('Hakeem Olajuwon', 'dream shake highlights', REVERED),
        ('LeBron James', 'chase down block and best plays', GREAT),
        ('Stephen Curry', 'deep threes highlights', REVERED),
        ('Victor Wembanyama', 'highlights', RISING),
        ('Shai Gilgeous-Alexander', 'highlights', RISING),
        ('Anthony Edwards', 'dunks highlights', RISING),
        ('Caitlin Clark', 'logo threes highlights', RISING),
        ('A\'ja Wilson', 'highlights', RISING),
    ],
    'Baseball': [
        ('Jackie Robinson', 'Dodgers history', GREAT),
        ('Negro Leagues', 'baseball history Satchel Paige Josh Gibson', GREAT),
        ('Willie Mays', 'the catch and highlights', GREAT),
        ('Hank Aaron', '715th home run', GREAT),
        ('Ken Griffey Jr', 'the kid highlights', REVERED),
        ('Rickey Henderson', 'stolen bases highlights', REVERED),
        ('Derek Jeter', 'the flip play and highlights', REVERED),
        ('Kirk Gibson', '1988 World Series home run', REVERED),
        ('Shohei Ohtani', 'two way highlights', RISING),
        ('Paul Skenes', 'strikeouts highlights', RISING),
        ('Elly De La Cruz', 'highlights', RISING),
        ('Aaron Judge', 'home runs highlights', RISING),
    ],
    'Hockey': [
        ('Wayne Gretzky', 'Oilers highlights', GREAT),
        ('Mario Lemieux', 'Penguins highlights', GREAT),
        ('Bobby Orr', 'flying goal 1970', GREAT),
        ('Miracle on Ice', '1980 USA USSR', GREAT),
        ('Pavel Bure', 'Russian rocket highlights', REVERED),
        ('Sidney Crosby', 'golden goal 2010', REVERED),
        ('Alex Ovechkin', 'best goals', REVERED),
        ('Connor McDavid', 'highlights', RISING),
        ('Connor Bedard', 'highlights', RISING),
        ('Macklin Celebrini', 'highlights', RISING),
    ],
    'Tennis': [
        ('Borg McEnroe', '1980 Wimbledon final tiebreak', GREAT),
        ('Arthur Ashe', '1975 Wimbledon final', GREAT),
        ('Serena Williams', 'best points', GREAT),
        ('Venus Williams', 'Wimbledon highlights', GREAT),
        ('Federer Nadal', '2008 Wimbledon final highlights', GREAT),
        ('Novak Djokovic', 'best points', GREAT),
        ('Steffi Graf', 'golden slam highlights', REVERED),
        ('Andre Agassi', 'best points', REVERED),
        ('Carlos Alcaraz', 'best points', RISING),
        ('Jannik Sinner', 'best points', RISING),
        ('Coco Gauff', 'best points', RISING),
        ('Aryna Sabalenka', 'highlights', RISING),
    ],
    'Rugby': [
        ('Jonah Lomu', '1995 World Cup England', GREAT),
        ('Springboks', '1995 Rugby World Cup final Mandela', GREAT),
        ('All Blacks', 'greatest haka', GREAT),
        ('Gareth Edwards', 'the greatest try 1973 Barbarians', GREAT),
        ('Brian O\'Driscoll', 'best tries', REVERED),
        ('Dan Carter', 'masterclass 2005 Lions', REVERED),
        ('Siya Kolisi', 'Springboks 2019 World Cup', REVERED),
        ('Antoine Dupont', 'highlights', RISING),
        ('Cheslin Kolbe', 'tries highlights', RISING),
        ('Louis Bielle-Biarrey', 'tries', RISING),
    ],
    'Cricket': [
        ('Viv Richards', 'West Indies batting highlights', GREAT),
        ('West Indies', '1970s 1980s fast bowlers Holding Marshall', GREAT),
        ('Sachin Tendulkar', 'best innings', GREAT),
        ('Brian Lara', '400 not out', GREAT),
        ('Shane Warne', 'ball of the century', GREAT),
        ('Wasim Akram', 'swing bowling', REVERED),
        ('Virat Kohli', 'chase masterclass', REVERED),
        ('Jasprit Bumrah', 'yorkers highlights', RISING),
        ('Yashasvi Jaiswal', 'highlights', RISING),
        ('Shubman Gill', 'centuries', RISING),
    ],
    'Track & field': [
        ('Jesse Owens', '1936 Berlin Olympics', GREAT),
        ('Florence Griffith Joyner', '100m world record 1988', GREAT),
        ('Carl Lewis', 'long jump and 100m', GREAT),
        ('Michael Johnson', '200m Atlanta 1996', GREAT),
        ('Usain Bolt', '9.58 Berlin 2009', GREAT),
        ('Haile Gebrselassie', '10000m Olympic final', REVERED),
        ('Kenenisa Bekele', '10000m world record', REVERED),
        ('Faith Kipyegon', '1500m world record', REVERED),
        ('Mondo Duplantis', 'pole vault world record', RISING),
        ('Sydney McLaughlin-Levrone', '400m hurdles world record', RISING),
        ('Julien Alfred', 'Olympic 100m gold', RISING),
    ],
}


def follow(k):
    return (settings.get('sports_follow') or {}).get(k) or FOLLOW[k]


def clip_key(c):
    return f"{c['artist']} {c['title']}".lower()


def clips(sports, rng, n, aired):
    """n clips across these sports: not aired in the last two weeks, one great or revered for every rising star,
    no player twice."""
    import time
    pool = [{'artist': w, 'title': t, 'tier': tier, 'sport': s} for s in sports for w, t, tier in CLIPS.get(s, [])]
    fresh = [c for c in pool if time.time() - aired.get(clip_key(c), 0) > 14 * 86400] or pool
    rng.shuffle(fresh)
    out, seen = [], set()
    for want_rising in [False, True] * n:  # a great first, then a rising star, and so on
        c = next((c for c in fresh if (c['tier'] == RISING) == want_rising and c['artist'] not in seen), None)
        if c:
            seen.add(c['artist'])
            out.append(c)
        if len(out) == n:
            break
    return out


def pick_desk(rng, at):
    """Which desk opens the next segment: the ones in season far likelier, the NFL on Sunday afternoons."""
    d = datetime.fromtimestamp(at)
    w = {'nfl': 1, 'club': 1, 'worldcup': 1, 'scoreboard': 3, 'world': 2}
    for k, months in SEASON.items():
        if d.month in months:
            w[k] = 4
    if d.month in SEASON['nfl'] and d.weekday() == 6 and 13 <= d.hour < 24:
        w['nfl'] = 12
    if d.month in SEASON['club'] and d.weekday() >= 5 and 7 <= d.hour < 17:
        w['club'] = 8
    k = rng.choices(list(w), list(w.values()))[0]
    return f'club:{rng.choice(LEAGUES)}' if k == 'club' else k


def weekend_boost(weights, at):
    """Saturday and Sunday afternoons are for sports."""
    d = datetime.fromtimestamp(at)
    if d.weekday() >= 5 and 12 <= d.hour < 19:
        weights = dict(weights, sports=4)
    return weights


# ---------------------------------------------------------------- the desks

def _when(iso):
    try:
        t = datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone()
    except (ValueError, AttributeError):
        return ''
    return t.strftime('%a %-I:%M %p').replace(':00 ', ' ')


def _model(m, home, away):
    if not m:
        return ''
    if 'draw' in m:
        return f"Model: {home} {m['home']}% · draw {m['draw']}% · {away} {m['away']}%"
    return ''


def _talk_point(p, nfl):
    """One talking point from NFL or Club Football Intelligence, as a line for the screen."""
    home, away, score = p.get('home'), p.get('away'), p.get('score')
    if home and away and score:
        a, b = (score.split('-') + [''])[:2]
        text = f'{away} {a}, {home} {b}' if nfl else f'{home} {score} {away}'
    elif home and away:
        text = f'{away} at {home}' if nfl else f'{home} v {away}'
    else:
        text = p.get('text', '')
    if p['kind'] in ('result', 'fixture', 'game', 'note', 'table', 'story') and p.get('text'):
        text = p['text']
    sub = p.get('detail') or ''
    if sub.lower() in ('final', 'ft'):
        sub = ''
    if p['kind'] == 'live' and p.get('situation', {}).get('downDistance'):
        sub = f"{sub} · {p['situation']['downDistance']}"
    if not score and p.get('kickoff') and p['kind'] in ('team', 'fixture', 'game'):
        sub = ' · '.join(x for x in (_when(p['kickoff']), _model(p.get('model'), home, away), sub) if x)
    tag = {'live': 'Live', 'result': 'Final', 'fixture': 'Next round', 'game': 'This week', 'table': 'The table',
           'story': 'The story', 'note': 'The read', 'team': 'Following'}.get(p['kind'], p['kind'].title())
    if p['kind'] == 'team':
        tag = f"Following · {p.get('team', '')}"
        if score:
            tag += ' · Final' if (p.get('detail') or '').upper() in ('FT', 'FINAL', 'AET', 'PEN') else ''
    logos = [x for x in (p.get('homeLogo'), p.get('awayLogo')) if x]
    if nfl:
        logos.reverse()  # away first, as the line reads
    return {'tag': tag, 'text': text, 'sub': sub, 'logos': logos}


def _talk(url, nfl):
    d = sources._get_json(url, timeout=40)  # the Intelligence sites sleep when idle on Render; give them time to wake
    seen, out = set(), []
    order = {'live': 0, 'team': 1, 'result': 2, 'story': 3, 'table': 4, 'game': 5, 'fixture': 5, 'note': 6}
    for p in sorted(d.get('points', []), key=lambda p: order.get(p['kind'], 9)):
        key = (p.get('home'), p.get('away'), p.get('score')) if p.get('home') else p.get('text')  # a game once, live or followed
        if key in seen:
            continue
        seen.add(key)
        out.append(_talk_point(p, nfl))
    return out, d.get('competitionName') or (f"Week {d['week']}" if d.get('week') else '')


def _nfl():
    pts, sub = _talk(f"{NFLI}/api/talk?follow={','.join(follow('nfl'))}", True)
    return pts, sub


def _club(league):
    q = urllib.parse.urlencode({'competition': league, 'follow': ','.join(follow('club'))})
    return _talk(f'{CFI}/api/talk?{q}', False)


def _worldcup():
    """World Cup 2026, the road back from the final."""
    teams = {t['id']: t for t in sources._get_json(f'{WCI}/api/teams', timeout=40)['data']}
    ms = sources._get_json(f'{WCI}/api/matches?status=FINISHED', timeout=40)['data']
    name = lambda i: (teams.get(i) or {}).get('name', i.upper())
    stage = {'FINAL': 'The final', 'THIRD_PLACE': 'Third place', 'SF': 'Semi-final', 'QF': 'Quarter-final',
             'R16': 'Round of 16', 'R32': 'Round of 32', 'GROUP': 'Group stage'}
    ko = [m for m in ms if m['stage'] != 'GROUP']
    ko.sort(key=lambda m: m['kickoff'], reverse=True)
    big = sorted((m for m in ms if m['stage'] == 'GROUP'), key=lambda m: -abs((m['homeScore'] or 0) - (m['awayScore'] or 0)))
    out = []
    for m in ko[:6] + big[:2]:
        pens = m.get('penalties')
        out.append({'tag': stage.get(m['stage'], m['stage'].title()) + (f" · Group {m['groupId']}" if m.get('groupId') else ''),
                    'text': f"{name(m['homeTeamId'])} {m['homeScore']}-{m['awayScore']} {name(m['awayTeamId'])}",  # no flag emoji: the TV can't draw them
                    'sub': ' · '.join(x for x in (m.get('venue'), m.get('city'), datetime.fromisoformat(m['kickoff']).strftime('%-d %B %Y'),
                                                   f'pens {pens}' if pens else '') if x), 'logos': []})
    if ko and ko[0]['stage'] == 'FINAL':
        f = ko[0]
        champ = f['homeTeamId'] if (f['homeScore'] or 0) > (f['awayScore'] or 0) else f['awayTeamId']
        out.insert(0, {'tag': 'Champions', 'text': f"{name(champ)}, world champions", 'sub': 'World Cup 2026 · USA · Canada · Mexico', 'logos': []})
    return out, 'World Cup 2026, revisited'


def _scoreboard():
    out = []
    for sport, league, label in (('basketball', 'nba', 'NBA'), ('hockey', 'nhl', 'NHL'), ('baseball', 'mlb', 'MLB')):
        try:
            evs = sources._get_json(f'{ESPN}/{sport}/{league}/scoreboard')['events']
        except Exception:
            continue
        mine = set(follow(league))
        rows = []
        for e in evs:
            c = e['competitions'][0]
            side = {x['homeAway']: x for x in c['competitors']}
            if 'home' not in side or 'away' not in side:
                continue
            st = e['status']['type']
            h, a = side['home'], side['away']
            abbrs = {h['team'].get('abbreviation'), a['team'].get('abbreviation')}
            if st['state'] == 'pre':
                text = f"{a['team']['shortDisplayName']} at {h['team']['shortDisplayName']}"
            else:
                text = f"{a['team']['shortDisplayName']} {a.get('score', '')}, {h['team']['shortDisplayName']} {h.get('score', '')}"
            tag = label + (' · Live' if st['state'] == 'in' else ' · Final' if st['completed'] else ' · Tonight' if st['state'] == 'pre' else '')
            if abbrs & mine:
                tag = f"Following · {tag}"
            rows.append((not (abbrs & mine), st['state'] != 'in', {'tag': tag, 'text': text, 'sub': '' if st['completed'] else st.get('shortDetail', ''),
                         'logos': [x for x in (a['team'].get('logo'), h['team'].get('logo')) if x]}))
        rows.sort(key=lambda r: r[:2])
        out += [r[2] for r in rows[:3]]
    return out, 'Last night and tonight'


def _world():
    feeds = [('Tennis', f'{ESPN}/tennis/atp/news'), ('Tennis', f'{ESPN}/tennis/wta/news'), ('Rugby', f'{ESPN}/rugby/164205/news'),
             ('Cricket', f'{ESPN}/cricket/8676/news')]
    out = []
    for label, url in feeds:
        try:
            arts = sources._get_json(url).get('articles', [])
        except Exception:
            continue
        out += [{'tag': label, 'text': x['headline'], 'sub': (x.get('description') or '')[:140], 'logos': []} for x in arts[:2]]
    try:  # boxing has no site feed; ESPN's headline service carries it
        heads = sources._get_json('https://now.core.api.espn.com/v1/sports/news?sport=boxing&limit=6').get('headlines', [])
        out += [{'tag': 'Boxing', 'text': x['headline'], 'sub': (x.get('description') or '')[:140], 'logos': []}
                for x in heads if 'list' not in x['headline'].lower()][:2]
    except Exception:
        pass
    random.Random(datetime.now().strftime('%Y%m%d%H')).shuffle(out)
    return out, 'Headlines'


def desk(name):
    """A desk's talking points: {desk, title, sub, from, points}. Cached a few minutes; a desk that can't be reached
    comes back empty and the segment goes straight to the tape."""
    k = name.split(':')[0]
    if k not in DESKS:
        return None
    title, src, _ = DESKS[k]
    build = {'nfl': _nfl, 'worldcup': _worldcup, 'scoreboard': _scoreboard, 'world': _world,
             'club': lambda: _club(name.split(':')[1] if ':' in name else LEAGUES[0])}[k]
    try:
        pts, sub = sources.cached('sports:' + name, 3 * 86400 if k == 'worldcup' else 240, lambda: list(build()))
    except Exception:
        pts, sub = [], ''
    return {'desk': name, 'title': title, 'sub': sub, 'from': src, 'points': pts[:8]}


def warm(name):
    """Fetch a desk in the background ahead of airtime, so the TV's request is answered from the cache."""
    threading.Thread(target=desk, args=(name,), daemon=True).start()
