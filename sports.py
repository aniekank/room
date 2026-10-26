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


def clips(sports, rng, n, aired, stars=()):
    """n clips for these sports: a player the numbers say is in form (when there is one), then turn and turn about
    a moment from the sport's whole history and a legend. Nothing aired in the last two weeks, nobody twice.
    History comes a decade at a time, chosen evenly, so the 1930s turn up as often as the 2010s."""
    import time
    from sports_history import HISTORY
    fresh = lambda c: time.time() - aired.get(clip_key(c), 0) > 14 * 86400
    legends = [{'artist': w, 'title': t, 'tier': tier, 'sport': s} for s in sports for w, t, tier in CLIPS.get(s, [])]
    history = [{'artist': w, 'title': t, 'tier': e, 'sport': s} for s in sports for w, t, e in HISTORY.get(s, [])]
    rng.shuffle(legends)
    out, seen, rising = [], set(), False

    def take(c):
        seen.add(c['artist'])
        out.append(c)

    in_form = [s for s in stars if s[2] in sports and s[0] not in seen]
    if in_form and n:
        who, note, sport = rng.choice(in_form)
        take({'artist': who, 'title': f'{datetime.now().year} highlights', 'tier': 'In form', 'note': note, 'sport': sport})
    slot = 'history'
    while len(out) < n:
        if slot == 'history' and history:
            eras = sorted({c['tier'] for c in history})
            pool = [c for c in history if c['tier'] == rng.choice(eras) and c['artist'] not in seen]
            c = rng.choice([c for c in pool if fresh(c)] or pool or [None])
        else:
            c = next((c for c in legends if (c['tier'] == RISING) == rising and c['artist'] not in seen and fresh(c)), None) \
                or next((c for c in legends if c['artist'] not in seen), None)
            rising = not rising
        if c:
            take(c)
        elif not history and not legends:
            break
        slot = 'legend' if slot == 'history' else 'history'
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
    """The games from a talk feed, followed teams first, each game once; and the feed itself for its leaders and boards."""
    d = sources._get_json(url, timeout=40)  # the Intelligence sites sleep when idle on Render; give them time to wake
    seen, out = set(), []
    order = {'live': 0, 'team': 1, 'result': 2, 'story': 3, 'table': 4, 'game': 5, 'fixture': 5, 'note': 6}
    for p in sorted(d.get('points', []), key=lambda p: order.get(p['kind'], 9)):
        key = (p.get('home'), p.get('away'), p.get('score')) if p.get('home') else p.get('text')  # a game once, live or followed
        if key in seen:
            continue
        seen.add(key)
        out.append(_talk_point(p, nfl))
    return d, out


def _num(v):
    if isinstance(v, float) and not v.is_integer():
        return f'{v:.1f}'
    return f'{int(v):,}'


def _low(stat):
    """'Passing TDs' -> 'passing TDs', for the middle of a sentence."""
    return ' '.join(w if w[1:2].isupper() else w.lower() for w in stat.split())


def _leaders(boards, league, sport):
    """Each stat's leader as a card (the next three underneath), and as a star the tape can show."""
    pts, stars = [], []
    for b in boards:
        rows = b.get('rows') or []
        if not rows:
            continue
        top = rows[0]
        pts.append({'tag': f"Leaders · {b['stat']}", 'text': f"{top['name']}, {top['team']} · {_num(top['value'])}",
                    'sub': 'then ' + ' · '.join(f"{r['name']} {_num(r['value'])}" for r in rows[1:4]) if len(rows) > 1 else '',
                    'logos': [top['teamLogo']] if top.get('teamLogo') else []})
        stars.append((top['name'], f"Leads {league} in {_low(b['stat'])} · {_num(top['value'])}", sport))
    return pts, stars


def _nfl():
    d, games = _talk(f"{NFLI}/api/talk?follow={','.join(follow('nfl'))}", True)
    insights, stars = _leaders(d.get('leaders') or [], 'the NFL', 'American football')
    b = d.get('board') or {}
    rk = b.get('rankings') or []
    if rk:
        insights.insert(1, {'tag': 'Power rankings', 'text': ' · '.join(f"{r['rank']}. {r['team']}" for r in rk[:4]),
                            'sub': "NFL Intelligence's efficiency model, offense and defense per play", 'logos': [r['logo'] for r in rk[:4] if r.get('logo')]})
    pj = b.get('projections') or []
    if pj:
        top = max(pj, key=lambda r: r['wins'])
        bubble = min(pj, key=lambda r: abs(r['playoff'] - 50))
        sims = f"{b['sims']:,} simulations" if b.get('sims') else 'the season simulation'
        insights.insert(3, {'tag': 'Projections', 'text': f"{top['team']} project to {top['wins']:.1f} wins",
                            'sub': f"{top['playoff']:.0f}% to make the playoffs · {top['division']:.0f}% to win the division · {sims}",
                            'logos': [top['logo']] if top.get('logo') else []})
        insights.insert(5, {'tag': 'On the bubble', 'text': f"{bubble['team']}: {bubble['playoff']:.0f}% to make the playoffs",
                            'sub': f"projected {bubble['wins']:.1f} wins · {sims}", 'logos': [bubble['logo']] if bubble.get('logo') else []})
    return {'games': games, 'insights': insights, 'stars': stars, 'sub': f"Week {d['week']}" if d.get('week') else ''}


def _club(league):
    q = urllib.parse.urlencode({'competition': league, 'follow': ','.join(follow('club'))})
    d, games = _talk(f'{CFI}/api/talk?{q}', False)
    name = d.get('competitionName') or league
    insights, stars = _leaders(d.get('leaders') or [], f'the {name}' if name.startswith('Premier') else name, 'Soccer')
    b = d.get('board') or {}
    pj = b.get('projections') or []
    if pj:
        odds = lambda key: ' · '.join(f"{r['team']} {r[key]:.0f}%" for r in sorted(pj, key=lambda r: -r[key])[:3])
        insights.insert(1, {'tag': 'Title odds', 'text': odds('title'), 'sub': 'Club Football Intelligence · the season simulated',
                            'logos': [r['logo'] for r in sorted(pj, key=lambda r: -r['title'])[:3] if r.get('logo')]})
        if any(r.get('releg') for r in pj):
            insights.insert(3, {'tag': 'Relegation danger', 'text': odds('releg'), 'sub': 'chance of going down, from the same simulation', 'logos': []})
    rk = b.get('rankings') or []
    if rk:
        insights.insert(2, {'tag': 'Power rankings', 'text': ' · '.join(f"{r['rank']}. {r['team']}" for r in rk[:4]),
                            'sub': "the model's rating of each side", 'logos': [r['logo'] for r in rk[:4] if r.get('logo')]})
    return {'games': games, 'insights': insights, 'stars': stars, 'sub': name}


def _worldcup():
    """World Cup 2026, the road back from the final, and the players who owned it."""
    teams = {t['id']: t for t in sources._get_json(f'{WCI}/api/teams', timeout=40)['data']}
    ms = sources._get_json(f'{WCI}/api/matches?status=FINISHED', timeout=40)['data']
    name = lambda i: (teams.get(i) or {}).get('name', i.upper())
    stage = {'FINAL': 'The final', 'THIRD_PLACE': 'Third place', 'SF': 'Semi-final', 'QF': 'Quarter-final',
             'R16': 'Round of 16', 'R32': 'Round of 32', 'GROUP': 'Group stage'}
    ko = [m for m in ms if m['stage'] != 'GROUP']
    ko.sort(key=lambda m: m['kickoff'], reverse=True)
    big = sorted((m for m in ms if m['stage'] == 'GROUP'), key=lambda m: -abs((m['homeScore'] or 0) - (m['awayScore'] or 0)))
    games = []
    for m in ko[:5] + big[:1]:
        pens = m.get('penalties')
        games.append({'tag': stage.get(m['stage'], m['stage'].title()) + (f" · Group {m['groupId']}" if m.get('groupId') else ''),
                      'text': f"{name(m['homeTeamId'])} {m['homeScore']}-{m['awayScore']} {name(m['awayTeamId'])}",  # no flag emoji: the TV can't draw them
                      'sub': ' · '.join(x for x in (m.get('venue'), m.get('city'), datetime.fromisoformat(m['kickoff']).strftime('%-d %B %Y'),
                                                     f'pens {pens}' if pens else '') if x), 'logos': []})
    if ko and ko[0]['stage'] == 'FINAL':
        f = ko[0]
        champ = f['homeTeamId'] if (f['homeScore'] or 0) > (f['awayScore'] or 0) else f['awayTeamId']
        games.insert(0, {'tag': 'Champions', 'text': f"{name(champ)}, world champions", 'sub': 'World Cup 2026 · USA · Canada · Mexico', 'logos': []})
    insights, stars = [], []
    try:
        ps = [p for p in sources._get_json(f'{WCI}/api/players', timeout=40)['data'] if p.get('stats')]
    except Exception:
        ps = []
    for stat, label in (('goals', 'Golden Boot'), ('assists', 'Most assists'), ('keyPasses', 'Chances created'), ('saves', 'Most saves')):
        top = sorted(ps, key=lambda p: -(p['stats'].get(stat) or 0))[:4]
        if not top or not top[0]['stats'].get(stat):
            continue
        t0 = top[0]
        insights.append({'tag': f'Leaders · {label}', 'text': f"{t0['name']}, {t0['team']['name']} · {t0['stats'][stat]}",
                         'sub': 'then ' + ' · '.join(f"{p['name']} {p['stats'][stat]}" for p in top[1:]), 'logos': [t0['photo']] if t0.get('photo') else []})
        if stat in ('goals', 'assists'):
            stars.append((t0['name'], f"{label} at the 2026 World Cup · {t0['stats'][stat]} {stat}", 'World Cup'))
    best = sorted(ps, key=lambda p: -(p['stats'].get('formIndex') or 0))[:3]
    if best:
        insights.append({'tag': 'Form index', 'text': ' · '.join(f"{p['name']} {p['stats']['formIndex']}" for p in best),
                         'sub': "World Cup Intelligence's rating of the tournament's best performers", 'logos': []})
    return {'games': games, 'insights': insights, 'stars': stars, 'sub': 'World Cup 2026, revisited'}


ESPN_LEADERS = {'nba': ('basketball', 'NBA', 'Basketball', ('Points Per Game', 'Assists Per Game', 'Rebounds Per Game')),
                'nhl': ('hockey', 'NHL', 'Hockey', ('Goals', 'Points')),
                'mlb': ('baseball', 'MLB', 'Baseball', ('Home Runs', 'Runs Batted In'))}


def _espn_leaders(league):
    sport, label, kind, cats = ESPN_LEADERS[league]
    d = sources._get_json(f'https://site.api.espn.com/apis/site/v3/sports/{sport}/{league}/leaders')
    pts, stars = [], []
    for c in (d.get('leaders') or {}).get('categories') or []:
        if c.get('displayName') not in cats or not c.get('leaders'):
            continue
        rows = [(l.get('athlete') or {}, l.get('value')) for l in c['leaders'][:4]]
        team = lambda a: (a.get('team') or {}).get('abbreviation', '') if isinstance(a.get('team'), dict) else ''
        a0, v0 = rows[0]
        if not a0.get('displayName') or v0 is None:
            continue
        pts.append({'tag': f"{label} leaders · {c['displayName']}", 'text': f"{a0['displayName']}{', ' + team(a0) if team(a0) else ''} · {_num(v0)}",
                    'sub': 'then ' + ' · '.join(f"{a.get('displayName')} {_num(v)}" for a, v in rows[1:] if v is not None),
                    'logos': [a0['headshot']['href']] if isinstance(a0.get('headshot'), dict) else []})
        stars.append((a0['displayName'], f"Leads the {label} in {_low(c['displayName'])} · {_num(v0)}", kind))
    return pts, stars


def _scoreboard():
    games, insights, stars = [], [], []
    month = datetime.now().month
    for sport, league, label in (('basketball', 'nba', 'NBA'), ('hockey', 'nhl', 'NHL'), ('baseball', 'mlb', 'MLB')):
        try:
            evs = sources._get_json(f'{ESPN}/{sport}/{league}/scoreboard')['events']
        except Exception:
            evs = []
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
        games += [r[2] for r in rows[:2]]
        if league == 'mlb' and not 3 <= month <= 10:
            continue  # last season's leaders are no news in the winter
        try:
            p, s = _espn_leaders(league)
            insights += p[:2]
            stars += s
        except Exception:
            pass
    return {'games': games, 'insights': insights, 'stars': stars, 'sub': 'Last night, tonight and the leaders'}


def _world():
    feeds = [('Tennis', f'{ESPN}/tennis/atp/news'), ('Tennis', f'{ESPN}/tennis/wta/news'), ('Rugby', f'{ESPN}/rugby/164205/news'),
             ('Cricket', f'{ESPN}/cricket/8676/news')]
    out = []
    for label, url in feeds:
        try:
            arts = sources._get_json(url).get('articles', [])
        except Exception:
            continue
        out += [{'tag': label, 'text': x['headline'], 'sub': (x.get('description') or '')[:140], 'logos': []} for x in arts[:3]]
    try:  # boxing has no site feed; ESPN's headline service carries it
        heads = sources._get_json('https://now.core.api.espn.com/v1/sports/news?sport=boxing&limit=6').get('headlines', [])
        out += [{'tag': 'Boxing', 'text': x['headline'], 'sub': (x.get('description') or '')[:140], 'logos': []}
                for x in heads if 'list' not in x['headline'].lower()][:2]
    except Exception:
        pass
    random.Random(datetime.now().strftime('%Y%m%d%H')).shuffle(out)
    return {'games': out, 'insights': [], 'stars': [], 'sub': 'Headlines'}


def _key(name):
    return 'sports2:' + name


def desk(name):
    """A desk's cards: the games first (followed teams leading), then the leaders and the models' reads.
    {desk, title, sub, from, points}. Cached a few minutes; a desk that can't be reached comes back empty and the
    segment goes straight to the tape."""
    k = name.split(':')[0]
    if k not in DESKS:
        return None
    title, src, _ = DESKS[k]
    build = {'nfl': _nfl, 'worldcup': _worldcup, 'scoreboard': _scoreboard, 'world': _world,
             'club': lambda: _club(name.split(':')[1] if ':' in name else LEAGUES[0])}[k]
    try:
        d = sources.cached(_key(name), 3 * 86400 if k == 'worldcup' else 240, build)
    except Exception:
        d = {'games': [], 'insights': [], 'sub': ''}
    pts = d['games'][:6] + d['insights'][:6] if d['insights'] else d['games'][:12]
    return {'desk': name, 'title': title, 'sub': d.get('sub', ''), 'from': src, 'points': pts}


def stars(name):
    """The players a desk's numbers say are in form, from the cache only: the schedule never waits on the network."""
    hit = sources._read().get(_key(name))
    return [tuple(s) for s in hit['v'].get('stars', [])] if hit else []


def warm(name):
    """Fetch a desk in the background ahead of airtime, so the TV's request is answered from the cache."""
    threading.Thread(target=desk, args=(name,), daemon=True).start()
