"""Personal choices live in data/settings.json; everything has a default so the file is optional.

  nag_time       "19:30"          when the daily Keys nudge fires (room install HH:MM also sets it)
  temp_unit      "F" or "C"       World Window weather
  cities         ["chicago", ...] which built-in World Window cities to use, in order (default: all)
  extra_cities   [{...}]          your own cities, same shape as sources.CITIES
  day_city       [7 city ids]     Monday-first weekday rotation (default: cycles through the cities)
  dig_lanes      ["Afrobeat", ...] which built-in Dig Tube lanes to search (default: all)
  extra_lanes    {"Lane": ["search", ...]}  your own Dig Tube lanes
  movies_folders ["~/Movies", ...] where the Movies channel looks, subfolders included (default: iCloud Drive/Movies)
  movies_courses ["*Hadoop*", ...] top folders that are courses: one group each, lessons in order, after the series
  movies_skip    ["*Udemy*", ...] folder or file names to leave out, * as a wildcard, any case; a leading / means
                                  only right inside one of your folders ("/Documents")
"""
import json

from paths import DATA

FILE = DATA / 'settings.json'

DEFAULTS = {
    'nag_time': '19:30',
    'temp_unit': 'F',
    'cities': None,
    'extra_cities': [],
    'day_city': None,
    'dig_lanes': None,
    'extra_lanes': {},
    'movies_folder': None,  # older single-folder form, still read
    'movies_folders': None,
    'movies_skip': [],
    'movies_courses': [],
}


def load():
    try:
        mine = json.loads(FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        mine = {}
    return dict(DEFAULTS, **mine)


def get(key):
    return load()[key]


def save(key, value):
    try:
        mine = json.loads(FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        mine = {}
    mine[key] = value
    FILE.write_text(json.dumps(mine, indent=2) + '\n')
