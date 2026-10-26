"""The FlyBoy Sports archive: every sport's whole history, as searches for its defining games.

Most of it is built from the calendar (every Super Bowl, NBA Finals, World Series, Stanley Cup Final, World Cup,
European Cup final, Wimbledon, Olympics...), so it reaches back to the newsreels and runs up to this year. The
fights, which don't fall on a calendar, are listed by hand. Each entry is (who, what to search for after it, era).
"""
from datetime import datetime

NOW = datetime.now().year


def roman(n):
    out = ''
    for v, s in ((50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while n >= v:
            out, n = out + s, n - v
    return out


def era(year):
    return f'The {year // 10 * 10}s'


def _every(start, end, step=1, skip=()):
    return [y for y in range(start, min(end, NOW) + 1, step) if y not in skip]


WC_YEARS = [1930, 1934, 1938] + _every(1950, 2026, 4)
AFCON_YEARS = [1957, 1959, 1962, 1963, 1965, 1968, 1970, 1972, 1974, 1976, 1978, 1980, 1982, 1984, 1986, 1988, 1990, 1992,
               1994, 1996, 1998, 2000, 2002, 2004, 2006, 2008, 2010, 2012, 2013, 2015, 2017, 2019, 2021, 2023, 2025]
OLYMPICS = [1896, 1900, 1904, 1908, 1912, 1920, 1924, 1928, 1932, 1936] + _every(1948, 2024, 4)
ASHES = ['1948', '1953', '1954-55', '1956', '1958-59', '1961', '1962-63', '1964', '1965-66', '1968', '1970-71', '1972',
         '1974-75', '1975', '1977', '1978-79', '1981', '1982-83', '1985', '1986-87', '1989', '1990-91', '1993', '1994-95',
         '1997', '1998-99', '2001', '2002-03', '2005', '2006-07', '2009', '2010-11', '2013', '2013-14', '2015', '2017-18',
         '2019', '2021-22', '2023', '2025-26']
LIONS = [1955, 1959, 1962, 1966, 1968, 1971, 1974, 1977, 1980, 1983, 1989, 1993, 1997, 2001, 2005, 2009, 2013, 2017, 2021, 2025]

FIGHTS = [  # (who, the fight, year)
    ('Jack Johnson', 'vs James J. Jeffries fight of the century', 1910),
    ('Jack Dempsey', 'vs Jess Willard Toledo', 1919),
    ('Jack Dempsey', 'vs Luis Firpo', 1923),
    ('Gene Tunney', 'vs Jack Dempsey long count', 1927),
    ('Joe Louis', 'vs Max Schmeling rematch', 1938),
    ('Joe Louis', 'vs Billy Conn', 1941),
    ('Sugar Ray Robinson', 'vs Jake LaMotta St Valentine\'s Day Massacre', 1951),
    ('Rocky Marciano', 'vs Jersey Joe Walcott', 1952),
    ('Floyd Patterson', 'vs Ingemar Johansson', 1960),
    ('Sonny Liston', 'vs Floyd Patterson', 1962),
    ('Cassius Clay', 'vs Sonny Liston', 1964),
    ('Muhammad Ali', 'vs Joe Frazier fight of the century', 1971),
    ('George Foreman', 'vs Joe Frazier Kingston', 1973),
    ('Muhammad Ali', 'vs Joe Frazier Thrilla in Manila', 1975),
    ('Larry Holmes', 'vs Ken Norton', 1978),
    ('Sugar Ray Leonard', 'vs Roberto Duran', 1980),
    ('Salvador Sanchez', 'vs Wilfredo Gomez', 1981),
    ('Sugar Ray Leonard', 'vs Thomas Hearns', 1981),
    ('Aaron Pryor', 'vs Alexis Arguello', 1982),
    ('Marvin Hagler', 'vs Thomas Hearns', 1985),
    ('Mike Tyson', 'vs Trevor Berbick', 1986),
    ('Sugar Ray Leonard', 'vs Marvin Hagler', 1987),
    ('Mike Tyson', 'vs Michael Spinks', 1988),
    ('Buster Douglas', 'vs Mike Tyson Tokyo', 1990),
    ('Julio Cesar Chavez', 'vs Meldrick Taylor', 1990),
    ('Riddick Bowe', 'vs Evander Holyfield', 1992),
    ('Pernell Whitaker', 'vs Julio Cesar Chavez', 1993),
    ('George Foreman', 'vs Michael Moorer', 1994),
    ('Evander Holyfield', 'vs Mike Tyson', 1996),
    ('Naseem Hamed', 'vs Kevin Kelley', 1997),
    ('Erik Morales', 'vs Marco Antonio Barrera', 2000),
    ('Arturo Gatti', 'vs Micky Ward', 2002),
    ('Lennox Lewis', 'vs Mike Tyson', 2002),
    ('Diego Corrales', 'vs Jose Luis Castillo', 2005),
    ('Floyd Mayweather', 'vs Oscar De La Hoya', 2007),
    ('Joe Calzaghe', 'vs Mikkel Kessler', 2007),
    ('Manny Pacquiao', 'vs Ricky Hatton', 2009),
    ('Juan Manuel Marquez', 'vs Manny Pacquiao IV', 2012),
    ('Floyd Mayweather', 'vs Canelo Alvarez', 2013),
    ('Gennady Golovkin', 'vs Canelo Alvarez', 2017),
    ('Anthony Joshua', 'vs Wladimir Klitschko', 2017),
    ('Andy Ruiz', 'vs Anthony Joshua', 2019),
    ('Tyson Fury', 'vs Deontay Wilder III', 2021),
    ('Naoya Inoue', 'vs Stephen Fulton', 2023),
    ('Terence Crawford', 'vs Errol Spence', 2023),
    ('Oleksandr Usyk', 'vs Tyson Fury', 2024),
    ('Terence Crawford', 'vs Canelo Alvarez', 2025),
]

MOMENTS = {  # games the calendar can't find
    'American football': [('The Ice Bowl', 'Packers Cowboys 1967', 1967), ('The Immaculate Reception', 'Franco Harris 1972', 1972),
                          ('The Catch', 'Dwight Clark 1982', 1982), ('The Music City Miracle', '2000', 2000),
                          ('The Helmet Catch', 'David Tyree Super Bowl XLII', 2008), ('The Kick Six', 'Auburn Alabama 2013', 2013),
                          ('Boise State', 'Fiesta Bowl 2007 Oklahoma', 2007), ('Texas USC', '2006 Rose Bowl Vince Young', 2006)],
    'Basketball': [('Dream Team', '1992 Olympics', 1992), ('Wilt Chamberlain', '100 point game', 1962),
                   ('Willis Reed', '1970 Game 7 walks out', 1970), ('Magic Johnson', '1980 Finals Game 6 at center', 1980),
                   ('Dominique Wilkins Larry Bird', '1988 Game 7 duel', 1988), ('Reggie Miller', '8 points in 9 seconds', 1995),
                   ('Ray Allen', '2013 Finals Game 6 corner three', 2013), ('Kyrie Irving', '2016 Finals Game 7 shot', 2016)],
    'Hockey': [('Summit Series', '1972 Canada USSR Henderson goal', 1972), ('Canada Cup', '1987 Gretzky Lemieux', 1987),
               ('Miracle on Ice', '1980 USA USSR', 1980), ('Easter Epic', '1987 Islanders Capitals', 1987)],
    'Soccer': [('Istanbul', '2005 Champions League final Liverpool Milan', 2005), ('Camp Nou', '1999 Champions League final Manchester United', 1999),
               ('Aguerooo', 'Manchester City 2012 title goal', 2012), ('Leicester City', '2016 champions season', 2016),
               ('Arsenal', 'Invincibles 2003-04', 2004), ('Barcelona 6-1 PSG', '2017', 2017)],
    'World Cup': [('Hungary', 'Magical Magyars 1954', 1954), ('Garrincha', '1962 World Cup', 1962), ('Eusebio', '1966 World Cup', 1966),
                  ('Italy West Germany', '1970 game of the century', 1970), ('Johan Cruyff', '1974 World Cup turn', 1974),
                  ('Paolo Rossi', '1982 World Cup Brazil', 1982), ('Senegal France', '2002 World Cup', 2002)],
    'Track & field': [('Bob Beamon', 'long jump 1968', 1968), ('Tommie Smith John Carlos', '1968 200m', 1968),
                      ('Wilma Rudolph', '1960 Rome', 1960), ('Abebe Bikila', 'barefoot marathon 1960', 1960),
                      ('Roger Bannister', 'four minute mile 1954', 1954), ('Derek Redmond', '1992 Barcelona', 1992),
                      ('Cathy Freeman', '400m Sydney 2000', 2000)],
    'Tennis': [('Billie Jean King', 'Battle of the Sexes 1973', 1973), ('Althea Gibson', 'Wimbledon 1957', 1957),
               ('Suzanne Lenglen', 'Wimbledon newsreel', 1925), ('Isner Mahut', '2010 Wimbledon longest match', 2010)],
    'Cricket': [('Don Bradman', 'batting footage', 1948), ('Kapil Dev', '175 not out 1983', 1983),
                ('Headingley 1981', 'Botham Ashes', 1981), ('Ben Stokes', 'Headingley 2019', 2019)],
    'Rugby': [('Barbarians', '1973 All Blacks', 1973), ('Japan South Africa', '2015 Brighton miracle', 2015),
              ('France New Zealand', '1999 World Cup semi final', 1999)],
}


def build():
    """{sport: [(who, what, era)]}, from the first recorded games to this year."""
    h = {s: [] for s in ('American football', 'Basketball', 'Baseball', 'Hockey', 'Soccer', 'World Cup', 'Boxing',
                         'Tennis', 'Rugby', 'Cricket', 'Track & field')}
    add = lambda s, who, what, y: h[s].append((who, what, era(y)))
    for y in _every(1933, 1965):
        add('American football', f'{y} NFL Championship Game', 'highlights', y)
    for n in range(1, NOW - 1966 + 1):
        add('American football', f'Super Bowl {roman(n)}', f'{1966 + n} highlights', 1966 + n)
    for y in _every(1999, NOW):
        add('American football', f'{y} college football national championship', 'highlights', y)
    for y in _every(1947, NOW):
        add('Basketball', f'{y} NBA Finals', 'highlights', y)
    for y in _every(1968, 1976):
        add('Basketball', f'{y} ABA Finals', 'highlights', y)
    for y in _every(1997, NOW - 1):
        add('Basketball', f'{y} WNBA Finals', 'highlights', y)
    for y in _every(1963, NOW):
        add('Basketball', f'{y} NCAA championship game', 'highlights', y)
    for y in _every(1903, NOW - 1, skip=(1904, 1994)):
        add('Baseball', f'{y} World Series', 'highlights', y)
    for y in _every(1933, NOW - 1, skip=(1945,)):
        add('Baseball', f'{y} MLB All-Star Game', 'highlights', y) if y < 1990 or y % 5 == 0 else None
    for y in _every(1920, 1948):
        add('Baseball', f'Negro Leagues {y}', 'baseball footage', y) if y % 4 == 0 else None
    for y in _every(1927, NOW, skip=(2005,)):
        add('Hockey', f'{y} Stanley Cup Final', 'highlights', y)
    for y in (1956, 1960, 1964, 1968, 1972, 1976, 1980, 1984, 1988, 1992, 1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026):
        add('Hockey', f'{y} Olympic hockey final', 'highlights', y)
    for y in _every(1956, NOW):
        add('Soccer', f"{y} {'European Cup' if y < 1993 else 'Champions League'} final", 'highlights', y)
    for y in _every(1923, NOW, skip=range(1940, 1946)):
        add('Soccer', f'{y} FA Cup final', 'highlights', y)
    for y in _every(1993, NOW):
        add('Soccer', f'Premier League {y - 1}-{str(y)[2:]}', 'season review', y)
    for y in _every(1960, NOW - 1):
        add('Soccer', f'{y} Copa Libertadores final', 'highlights', y)
    for y in AFCON_YEARS:
        add('Soccer', f'Africa Cup of Nations {y} final', 'highlights', y)
    for y in _every(1980, NOW - 1):
        add('Soccer', f'El Clasico {y}', 'Real Madrid Barcelona highlights', y)
    for y in _every(1960, 2024, 4):
        add('World Cup', f'Euro {y} final', 'highlights', y)
    for y in WC_YEARS:
        add('World Cup', f'{y} World Cup final', 'highlights', y)
        add('World Cup', f'{y} World Cup', 'best goals', y)
    for y in (1991, 1995, 1999, 2003, 2007, 2011, 2015, 2019, 2023):
        add('World Cup', f"{y} Women's World Cup final", 'highlights', y)
    for who, what, y in FIGHTS:
        add('Boxing', who, f'{what} {y}', y)
    for y in _every(1920, NOW, skip=range(1940, 1946)):
        add('Tennis', f'Wimbledon {y}', "men's final", y)
        if y >= 1968:
            add('Tennis', f'Wimbledon {y}', "women's final", y)
    for y in _every(1968, NOW):
        add('Tennis', f'US Open {y}', "men's final", y)
        add('Tennis', f'US Open {y}', "women's final", y)
    for y in (1987, 1991, 1995, 1999, 2003, 2007, 2011, 2015, 2019, 2023):
        add('Rugby', f'{y} Rugby World Cup final', 'highlights', y)
    for y in LIONS:
        add('Rugby', f'British and Irish Lions {y}', 'tour highlights', y)
    for y in _every(1970, NOW):
        add('Rugby', f"{'Five' if y < 2000 else 'Six'} Nations {y}", 'best tries', y)
    for y in (1975, 1979, 1983, 1987, 1992, 1996, 1999, 2003, 2007, 2011, 2015, 2019, 2023):
        add('Cricket', f'{y} Cricket World Cup final', 'highlights', y)
    for y in (2007, 2009, 2010, 2012, 2014, 2016, 2021, 2022, 2024, 2026):
        add('Cricket', f'{y} T20 World Cup final', 'highlights', y)
    for s in ASHES:
        add('Cricket', f'The Ashes {s}', 'highlights', int(s[:4]))
    for y in OLYMPICS:
        add('Track & field', f"{y} Olympics men's 100m final", '', y)
        if y >= 1928:
            add('Track & field', f"{y} Olympics women's 100m final", '', y)
        if y >= 1948:
            add('Track & field', f'{y} Olympics athletics', 'highlights', y)
    for y in [1983, 1987] + _every(1991, NOW, 2):
        add('Track & field', f'{y} World Athletics Championships', '100m final', y)
    for s, ms in MOMENTS.items():
        for who, what, y in ms:
            add(s, who, what, y)
    return h


HISTORY = build()
