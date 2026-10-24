"""The sample crate: records with something to flip (breaks, chords, strings, a vocal), aired in From the Crates
alongside the digging list.
Covers come from the iTunes Search API, looked up once in the background and kept in data/funk_art.json.
"""
import json
import threading
import time
import urllib.parse
import urllib.request

from paths import DATA

ART = DATA / 'funk_art.json'
UA = {'User-Agent': 'Room/1.0 (personal TV channels)'}

# (artist, song, year, lane)
RECORDS = [
    # the foundation
    ('James Brown', 'Funky Drummer', 1970, 'Raw funk'),
    ('James Brown', 'Get Up (I Feel Like Being a) Sex Machine', 1970, 'Raw funk'),
    ('James Brown', 'The Payback', 1973, 'Raw funk'),
    ('The J.B.\'s', 'Doing It to Death', 1973, 'Raw funk'),
    ('Lyn Collins', 'Think (About It)', 1972, 'Raw funk'),
    ('Sly & the Family Stone', 'Thank You (Falettinme Be Mice Elf Agin)', 1969, 'Raw funk'),
    ('Sly & the Family Stone', 'If You Want Me to Stay', 1973, 'Raw funk'),
    ('The Meters', 'Cissy Strut', 1969, 'New Orleans funk'),
    ('The Meters', 'Look-Ka Py Py', 1969, 'New Orleans funk'),
    ('The Meters', 'Hand Clapping Song', 1970, 'New Orleans funk'),
    ('Dr. John', 'Right Place Wrong Time', 1973, 'New Orleans funk'),
    ('Allen Toussaint', 'Night People', 1978, 'New Orleans funk'),
    ('Funkadelic', 'One Nation Under a Groove', 1978, 'P-Funk'),
    ('Parliament', 'Flash Light', 1977, 'P-Funk'),
    ('Parliament', 'Give Up the Funk (Tear the Roof off the Sucker)', 1975, 'P-Funk'),
    ('Bootsy\'s Rubber Band', 'I\'d Rather Be with You', 1976, 'P-Funk'),
    ('Zapp', 'More Bounce to the Ounce', 1980, 'P-Funk'),
    ('Ohio Players', 'Funky Worm', 1973, 'Band funk'),
    ('Ohio Players', 'Love Rollercoaster', 1975, 'Band funk'),
    ('Kool & the Gang', 'Jungle Boogie', 1973, 'Band funk'),
    ('Kool & the Gang', 'Summer Madness', 1974, 'Band funk'),
    ('The Isley Brothers', 'Fight the Power', 1975, 'Band funk'),
    ('The Isley Brothers', 'Footsteps in the Dark', 1977, 'Band funk'),
    ('Earth, Wind & Fire', 'Shining Star', 1975, 'Band funk'),
    ('Earth, Wind & Fire', 'Getaway', 1976, 'Band funk'),
    ('Tower of Power', 'What Is Hip?', 1973, 'Band funk'),
    ('War', 'Low Rider', 1975, 'Band funk'),
    ('War', 'The World Is a Ghetto', 1972, 'Band funk'),
    ('Rufus & Chaka Khan', 'Tell Me Something Good', 1974, 'Band funk'),
    ('The Commodores', 'Brick House', 1977, 'Band funk'),
    ('Slave', 'Slide', 1977, 'Band funk'),
    ('Cameo', 'Candy', 1986, 'Band funk'),
    ('Rick James', 'Give It to Me Baby', 1981, 'Band funk'),
    ('Prince', 'Controversy', 1981, 'Minneapolis'),
    ('The Time', 'Jungle Love', 1984, 'Minneapolis'),
    ('Stevie Wonder', 'Superstition', 1972, 'Soul-funk'),
    ('Stevie Wonder', 'Higher Ground', 1973, 'Soul-funk'),
    ('Curtis Mayfield', 'Move On Up', 1970, 'Soul-funk'),
    ('Curtis Mayfield', 'Pusherman', 1972, 'Soul-funk'),
    ('Marvin Gaye', 'Got to Give It Up', 1977, 'Soul-funk'),
    ('Bill Withers', 'Use Me', 1972, 'Soul-funk'),
    ('Betty Davis', 'If I\'m in Luck I Might Get Picked Up', 1973, 'Soul-funk'),
    ('Labelle', 'Lady Marmalade', 1974, 'Soul-funk'),
    ('Shuggie Otis', 'Inspiration Information', 1974, 'Soul-funk'),
    # breaks and rare groove: the records producers dig for
    ('The Incredible Bongo Band', 'Apache', 1973, 'Breaks'),
    ('The Winstons', 'Amen, Brother', 1969, 'Breaks'),
    ('The Honey Drippers', 'Impeach the President', 1973, 'Breaks'),
    ('Melvin Bliss', 'Synthetic Substitution', 1973, 'Breaks'),
    ('Skull Snaps', 'It\'s a New Day', 1973, 'Breaks'),
    ('Bob James', 'Nautilus', 1974, 'Breaks'),
    ('Dennis Coffey', 'Scorpio', 1971, 'Breaks'),
    ('Jimmy Castor Bunch', 'It\'s Just Begun', 1972, 'Breaks'),
    ('Baby Huey', 'Hard Times', 1971, 'Breaks'),
    ('Mountain', 'Long Red', 1972, 'Breaks'),
    ('The Mohawks', 'The Champ', 1968, 'Breaks'),
    ('Charles Wright & the Watts 103rd Street Rhythm Band', 'Express Yourself', 1970, 'Breaks'),
    ('Cymande', 'Bra', 1972, 'Rare groove'),
    ('Cymande', 'Dove', 1972, 'Rare groove'),
    ('Darondo', 'Didn\'t I', 1973, 'Rare groove'),
    ('Lee Moses', 'Bad Girl', 1971, 'Rare groove'),
    ('Ann Peebles', 'I Can\'t Stand the Rain', 1973, 'Rare groove'),
    ('Syl Johnson', 'Is It Because I\'m Black', 1969, 'Rare groove'),
    ('Eddie Kendricks', 'Keep on Truckin\'', 1973, 'Rare groove'),
    ('Rotary Connection', 'Memory Band', 1971, 'Rare groove'),
    ('Kashmere Stage Band', 'Kashmere', 1971, 'Rare groove'),
    # jazz-funk
    ('Herbie Hancock', 'Chameleon', 1973, 'Jazz-funk'),
    ('Herbie Hancock', 'Watermelon Man', 1973, 'Jazz-funk'),
    ('Donald Byrd', 'Think Twice', 1975, 'Jazz-funk'),
    ('Roy Ayers Ubiquity', 'Everybody Loves the Sunshine', 1976, 'Jazz-funk'),
    ('Lonnie Liston Smith', 'Expansions', 1975, 'Jazz-funk'),
    ('The Blackbyrds', 'Rock Creek Park', 1975, 'Jazz-funk'),
    ('Grover Washington Jr.', 'Mister Magic', 1975, 'Jazz-funk'),
    ('Ronnie Laws', 'Always There', 1975, 'Jazz-funk'),
    ('George Duke', 'Reach for It', 1977, 'Jazz-funk'),
    ('Idris Muhammad', 'Could Heaven Ever Be Like This', 1977, 'Jazz-funk'),
    ('Weldon Irvine', 'I Love You', 1973, 'Jazz-funk'),
    ('Azymuth', 'Jazz Carnival', 1979, 'Jazz-funk'),
    # boogie and disco
    ('Chic', 'Good Times', 1979, 'Disco'),
    ('Chic', 'I Want Your Love', 1978, 'Disco'),
    ('Sister Sledge', 'He\'s the Greatest Dancer', 1979, 'Disco'),
    ('Donna Summer', 'I Feel Love', 1977, 'Disco'),
    ('Michael Jackson', 'Don\'t Stop \'til You Get Enough', 1979, 'Disco'),
    ('Teddy Pendergrass', 'Only You', 1978, 'Disco'),
    ('Cheryl Lynn', 'Got to Be Real', 1978, 'Disco'),
    ('Patrice Rushen', 'Forget Me Nots', 1982, 'Boogie'),
    ('Yarbrough & Peoples', 'Don\'t Stop the Music', 1980, 'Boogie'),
    ('D Train', 'You\'re the One for Me', 1981, 'Boogie'),
    ('Change', 'The Glow of Love', 1980, 'Boogie'),
    ('Mtume', 'Juicy Fruit', 1983, 'Boogie'),
    ('The Gap Band', 'Outstanding', 1982, 'Boogie'),
    ('The S.O.S. Band', 'Just Be Good to Me', 1983, 'Boogie'),
    ('Skyy', 'Call Me', 1981, 'Boogie'),
    ('Dinosaur L', 'Go Bang', 1982, 'Boogie'),
    ('ESG', 'Moody', 1981, 'Boogie'),
    # Brazil, Africa, Latin
    ('Jorge Ben', 'Taj Mahal', 1972, 'Brazil'),
    ('Tim Maia', 'Ela Partiu', 1971, 'Brazil'),
    ('Marcos Valle', 'Estrelar', 1983, 'Brazil'),
    ('Os Mutantes', 'A Minha Menina', 1968, 'Brazil'),
    ('Fela Kuti', 'Water No Get Enemy', 1975, 'Afrobeat'),
    ('Fela Kuti', 'Zombie', 1976, 'Afrobeat'),
    ('Tony Allen', 'Afro Disco Beat', 1979, 'Afrobeat'),
    ('William Onyeabor', 'Fantastic Man', 1977, 'Afrobeat'),
    ('Ebo Taylor', 'Heaven', 1980, 'Afrobeat'),
    ('Mulatu Astatke', 'Yègellé Tezeta', 1969, 'Ethio-jazz'),
    ('Manu Dibango', 'Soul Makossa', 1972, 'Afro-funk'),
    ('Joe Bataan', 'Ordinary Guy', 1967, 'Latin soul'),
    ('El Michels Affair', 'Detroit Twice', 2009, 'Latin soul'),
    ('Mongo Santamaría', 'Watermelon Man', 1963, 'Latin soul'),
    ('Ray Barretto', 'El Watusi', 1962, 'Latin soul'),
    ('Malo', 'Suavecito', 1972, 'Latin soul'),
    # soft rock and MOR: session-player chords producers keep going back to
    ('Steely Dan', 'Peg', 1977, 'Soft rock'),
    ('Steely Dan', 'Do It Again', 1972, 'Soft rock'),
    ('Michael McDonald', 'I Keep Forgettin\' (Every Time You\'re Near)', 1982, 'Soft rock'),
    ('The Doobie Brothers', 'What a Fool Believes', 1978, 'Soft rock'),
    ('Hall & Oates', 'I Can\'t Go for That (No Can Do)', 1981, 'Soft rock'),
    ('Toto', 'Georgy Porgy', 1978, 'Soft rock'),
    ('Fleetwood Mac', 'Dreams', 1977, 'Soft rock'),
    ('Bread', 'Make It with You', 1970, 'Soft rock'),
    ('Christopher Cross', 'Ride Like the Wind', 1979, 'Soft rock'),
    ('Kenny Loggins', 'This Is It', 1979, 'Soft rock'),
    ('Ambrosia', 'Biggest Part of Me', 1980, 'Soft rock'),
    ('Boz Scaggs', 'Lowdown', 1976, 'Soft rock'),
    ('Seals & Crofts', 'Summer Breeze', 1972, 'Soft rock'),
    ('America', 'Ventura Highway', 1972, 'Soft rock'),
    ('Carole King', 'It\'s Too Late', 1971, 'Soft rock'),
    ('Todd Rundgren', 'Hello It\'s Me', 1972, 'Soft rock'),
    ('Bill Withers', 'Lovely Day', 1977, 'Soft rock'),
    ('Alan Parsons Project', 'Mammagamma', 1982, 'Soft rock'),
    ('10cc', 'I\'m Not in Love', 1975, 'Soft rock'),
    ('Supertramp', 'Goodbye Stranger', 1979, 'Soft rock'),
    ('Gerry Rafferty', 'Baker Street', 1978, 'Soft rock'),
    ('Steve Miller Band', 'Fly Like an Eagle', 1976, 'Soft rock'),
    ('Rotary Connection', 'I Am the Black Gold of the Sun', 1971, 'Orchestral soul'),
    # orchestral soul: strings and horns made for chopping
    ('Isaac Hayes', 'Walk On By', 1969, 'Orchestral soul'),
    ('Isaac Hayes', 'Ike\'s Rap II', 1971, 'Orchestral soul'),
    ('Barry White', 'I\'m Gonna Love You Just a Little More Baby', 1973, 'Orchestral soul'),
    ('Love Unlimited Orchestra', 'Love\'s Theme', 1973, 'Orchestral soul'),
    ('The Delfonics', 'Didn\'t I (Blow Your Mind This Time)', 1970, 'Orchestral soul'),
    ('The Stylistics', 'People Make the World Go Round', 1972, 'Orchestral soul'),
    ('The Chi-Lites', 'Are You My Woman? (Tell Me So)', 1970, 'Orchestral soul'),
    ('The Dramatics', 'In the Rain', 1972, 'Orchestral soul'),
    ('Minnie Riperton', 'Inside My Love', 1975, 'Orchestral soul'),
    ('Al Green', 'Love and Happiness', 1972, 'Orchestral soul'),
    ('O.V. Wright', 'A Nickel and a Nail', 1971, 'Orchestral soul'),
    ('Gil Scott-Heron', 'The Bottle', 1974, 'Orchestral soul'),
    ('Lamont Dozier', 'Going Back to My Roots', 1977, 'Orchestral soul'),
    ('Willie Hutch', 'Brother\'s Gonna Work It Out', 1973, 'Orchestral soul'),
    ('Quincy Jones', 'Summer in the City', 1973, 'Orchestral soul'),
    # library and soundtracks: the producer's secret shelf
    ('David Axelrod', 'Holy Thursday', 1968, 'Library & soundtracks'),
    ('Galt MacDermot', 'Coffee Cold', 1966, 'Library & soundtracks'),
    ('Ennio Morricone', 'Il Clan dei Siciliani', 1969, 'Library & soundtracks'),
    ('Piero Umiliani', 'Mah Nà Mah Nà', 1968, 'Library & soundtracks'),
    ('Lalo Schifrin', 'Enter the Dragon', 1973, 'Library & soundtracks'),
    ('Roy Budd', 'Get Carter', 1971, 'Library & soundtracks'),
    ('Bob James', 'Take Me to the Mardi Gras', 1975, 'Library & soundtracks'),
    ('Willie Hutch', 'Theme of the Mack', 1973, 'Library & soundtracks'),
    ('Curtis Mayfield', 'Little Child Runnin\' Wild', 1972, 'Library & soundtracks'),
    ('Isaac Hayes', 'Theme from Shaft', 1971, 'Library & soundtracks'),
    ('Edwin Starr', 'Easin\' In', 1973, 'Library & soundtracks'),
    ('Ennio Morricone', 'Ecstasy of Gold', 1966, 'Library & soundtracks'),
    ('Keith Mansfield', 'Funky Fanfare', 1968, 'Library & soundtracks'),
    ('Serge Gainsbourg', 'Melody', 1971, 'Library & soundtracks'),
    ('Jean-Claude Vannier', 'L\'Enfant Assassin des Mouches', 1972, 'Library & soundtracks'),
    ('Lewis Taylor', 'Lucky', 1996, 'Soft rock'),
    # the new school: funk being made now
    ('Sharon Jones & the Dap-Kings', '100 Days, 100 Nights', 2007, 'Deep funk revival'),
    ('Charles Bradley', 'The World (Is Going Up in Flames)', 2011, 'Deep funk revival'),
    ('The Budos Band', 'Up from the South', 2005, 'Deep funk revival'),
    ('Lee Fields & the Expressions', 'Ladies', 2009, 'Deep funk revival'),
    ('Durand Jones & the Indications', 'Smile', 2018, 'Deep funk revival'),
    ('Menahan Street Band', 'Make the Road by Walking', 2008, 'Deep funk revival'),
    ('Khruangbin', 'Maria También', 2018, 'Modern funk'),
    ('Khruangbin & Leon Bridges', 'Texas Sun', 2020, 'Modern funk'),
    ('Thundercat', 'Them Changes', 2015, 'Modern funk'),
    ('Thundercat', 'Dragonball Durag', 2020, 'Modern funk'),
    ('Anderson .Paak', 'Come Down', 2016, 'Modern funk'),
    ('Silk Sonic', 'Fly as Me', 2021, 'Modern funk'),
    ('Vulfpeck', 'Dean Town', 2016, 'Modern funk'),
    ('Cory Wong', 'Golden', 2019, 'Modern funk'),
    ('Dam-Funk', 'Hood Pass Intact', 2009, 'Modern funk'),
    ('Chromeo', 'Jealous (I Ain\'t with It)', 2014, 'Modern funk'),
    ('Tuxedo', 'Do It', 2015, 'Modern funk'),
    ('Dâm-Funk & Snoop Dogg', 'Faden Away', 2013, 'Modern funk'),
    ('Childish Gambino', 'Me and Your Mama', 2016, 'Modern funk'),
    ('Kaytranada', 'Glowed Up', 2016, 'Modern funk'),
    ('Steve Lacy', 'Dark Red', 2017, 'Modern funk'),
    ('Moonchild', 'Cure', 2017, 'Modern funk'),
    ('Jungle', 'Busy Earnin\'', 2014, 'Modern funk'),
    ('Parcels', 'Tieduprightnow', 2018, 'Modern funk'),
    ('Yussef Dayes', 'Rust', 2023, 'Modern funk'),
    ('Kokoroko', 'Abusey Junction', 2018, 'Modern funk'),
    ('Ezra Collective', 'Victory Dance', 2022, 'Modern funk'),
    ('BADBADNOTGOOD', 'Time Moves Slow', 2016, 'Modern funk'),
    ('Mndsgn', 'Camelblues', 2016, 'Modern funk'),
    ('Sault', 'Wildfires', 2020, 'Modern funk'),
    ('Hiatus Kaiyote', 'Nakamarra', 2012, 'Modern funk'),
]


TAGS = DATA / 'crates_tags.json'  # digging-list artist -> MusicBrainz tags, for how sampleable a record is
# How likely a record is to give you something to sample: chords, strings, a break, a vocal to chop. Soft rock and
# MOR count: lush, played by session players, and mined by producers for decades.
SOUNDS = [  # (words in an artist's tags, score); the best match wins
    (('funk', 'soul', 'disco', 'boogie', 'groove', 'breaks', 'afro', 'jazz-funk', 'go-go'), 3),
    (('jazz', 'fusion', 'r&b', 'rhythm and blues', 'latin', 'salsa', 'boogaloo', 'bossa', 'mpb', 'samba', 'tropicalia',
      'library', 'soundtrack', 'score', 'psychedelic', 'exotica', 'lounge', 'yacht', 'soft rock', 'quiet storm', 'reggae',
      'dub', 'electro', 'hip hop', 'hip-hop', 'gospel', 'spiritual'), 2.4),
    (('easy listening', 'adult contemporary', 'orchestral', 'progressive', 'prog', 'singer-songwriter', 'pop rock',
      'folk rock', 'rock', 'pop', 'vocal', 'blues', 'world', 'electronic', 'synth'), 1.6),
    (('country', 'folk', 'classical', 'opera', 'bluegrass', 'christmas', 'musical', 'schlager', 'polka'), .7),
    (('comedy', 'spoken', 'children', 'novelty', 'barbershop'), .3),
]
LANE_SCORE = {'Soul, funk & R&B': 3, '12-inch singles & hip-hop': 2.6, 'Soul-jazz & jazz': 2.6, 'World & Latin': 2.4,
              'Scores & soundtracks': 2.4, 'MOR & soft rock': 2.2, 'Rock, prog & psych': 2.2, 'Easy listening & orchestral': 2,
              'Gospel & spiritual': 2, 'Pop & vocal': 1.6, 'Country & folk': .8, 'Classical': .8,
              'Comedy & spoken word': .4, "Children's": .3}


def _tags():
    try:
        return json.loads(TAGS.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _era(rec):
    """Records from the sampling sweet spot, 1966-1984, get a lift; anything after the mid-90s less of one."""
    try:
        y = int(str(rec.get('year') or '')[:4])
    except ValueError:
        return 1
    return 1.3 if 1966 <= y <= 1984 else 1.1 if 1958 <= y <= 1992 else .8


def score(rec):
    """How likely a record is to have something to sample, about 0.3 (a comedy LP) to 4: weights Crates' picks."""
    if rec.get('funk'):
        return rec['funk']
    lanes = [LANE_SCORE[l] for l in rec.get('lanes') or [] if l in LANE_SCORE]
    if lanes:
        return max(lanes) * _era(rec)
    tags = _tags().get(rec['artist'].lower())
    if not tags:
        return 1.4 * _era(rec)  # not looked up yet, or MusicBrainz has no tags: a fair chance
    t = ' '.join(tags).lower()
    return next((sc for words, sc in SOUNDS if any(w in t for w in words)), 1.2) * _era(rec)


def _mb_tags(artist):
    q = urllib.parse.urlencode({'query': f'artist:"{artist}"', 'fmt': 'json', 'limit': 1})
    req = urllib.request.Request('https://musicbrainz.org/ws/2/artist?' + q,
                                 headers={'User-Agent': 'Room/1.0 (https://github.com/aniekank/room)'})
    with urllib.request.urlopen(req, timeout=20) as r:
        hits = json.loads(r.read()).get('artists', [])
    if not hits or hits[0].get('score', 0) < 85:
        return []
    return [t['name'] for t in sorted(hits[0].get('tags', []), key=lambda t: -t.get('count', 0))[:10]]


def _tag_worker(artists, log):
    tags, n = _tags(), 0
    for a in artists:
        k = a.lower()
        if k in tags or k.startswith('various'):
            continue
        for _ in range(3):
            try:
                tags[k] = _mb_tags(a)
                break
            except Exception:
                time.sleep(5)  # MusicBrainz says 503 when it's busy
        n += 1
        if n % 20 == 0:
            TAGS.write_text(json.dumps(tags, indent=1))
        time.sleep(1.2)  # one request a second, as MusicBrainz asks
    TAGS.write_text(json.dumps(tags, indent=1))
    if n:
        log(f'funk: tagged {n} digging-list artists')


def _art():
    try:
        return json.loads(ART.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _key(artist, song):
    return f'{artist} {song}'.lower()


def records():
    """The funk crate as Crates records: only ones whose cover has been found, so the card always has a picture."""
    art = _art()
    out = []
    for artist, song, year, lane in RECORDS:
        img = art.get(_key(artist, song))
        if img:
            out.append({'id': 'funk:' + _key(artist, song), 'artist': artist, 'title': song, 'year': str(year),
                        'lane': lane, 'crate': 'The sample crate', 'img': img, 'funk': 3.6})
    return out


def _cover(artist, song):
    q = urllib.parse.urlencode({'term': f'{artist} {song}', 'entity': 'song', 'limit': 5})
    with urllib.request.urlopen(urllib.request.Request('https://itunes.apple.com/search?' + q, headers=UA), timeout=20) as r:
        hits = json.loads(r.read()).get('results', [])
    a = artist.lower().split(' & ')[0].replace('the ', '')[:8]
    hit = next((h for h in hits if a in h.get('artistName', '').lower()), hits[0] if hits else None)
    return (hit or {}).get('artworkUrl100', '').replace('100x100bb', '600x600bb')


def _worker(log):
    art, found = _art(), 0
    for artist, song, _, _ in RECORDS:
        k = _key(artist, song)
        if k in art:
            continue
        try:
            art[k] = _cover(artist, song)
        except Exception:
            time.sleep(60)
            continue
        found += bool(art[k])
        ART.write_text(json.dumps(art, indent=1))
        time.sleep(3)
    if found:
        log(f'funk: {found} covers found')


def start(artists, log=print):
    threading.Thread(target=_worker, args=(log,), daemon=True).start()
    threading.Thread(target=_tag_worker, args=(sorted(set(artists)), log), daemon=True).start()
