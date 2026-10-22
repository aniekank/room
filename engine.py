"""Keeps Room.app's yt-dlp current. YouTube changes often break old copies, and an app
can't pip install, so it fetches yt-dlp's official single-file release (a zip of the
Python package), checks it against the release's SHA2-256SUMS, and imports from that
instead of the copy bundled at build time.
"""
import hashlib
import importlib.abc
import importlib.machinery
import json
import sys
import time
import urllib.request
import zipfile

from paths import DATA

ZIP = DATA / 'yt-dlp.zip'
META = DATA / 'yt-dlp.json'
RELEASE = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/'
API = 'https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest'
UA = {'User-Agent': 'Room/1.0 (personal TV channels)'}


class _PreferZip(importlib.abc.MetaPathFinder):
    """Ahead of PyInstaller's importer, so yt_dlp and its submodules all load from the zip."""

    def find_spec(self, name, path, target=None):
        if name != 'yt_dlp' and not name.startswith('yt_dlp.'):
            return None
        return importlib.machinery.PathFinder.find_spec(name, path or [str(ZIP)])


def activate():
    """Call before anything imports yt_dlp."""
    if ZIP.exists() and zipfile.is_zipfile(ZIP) and 'yt_dlp' not in sys.modules:
        sys.meta_path.insert(0, _PreferZip())


def meta():
    try:
        return json.loads(META.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def version():
    """The version in use (the downloaded zip once activate() has run, else the bundled copy)."""
    try:
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return '?'


def _get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def update(force=False, log=print):
    """Download a newer yt-dlp if there is one. Returns the new version, or None.
    It takes effect the next time Room starts."""
    m = meta()
    if not force and time.time() - m.get('checked', 0) < 86400:
        return None
    latest = json.loads(_get(API))['tag_name']
    m['checked'] = time.time()
    if latest == version():
        META.write_text(json.dumps(m))
        return None
    sums = _get(RELEASE + 'SHA2-256SUMS').decode()
    want = next(line.split()[0] for line in sums.splitlines() if line.split()[-1] == 'yt-dlp')
    blob = _get(RELEASE + 'yt-dlp', timeout=120)
    if hashlib.sha256(blob).hexdigest() != want:
        raise RuntimeError('yt-dlp download did not match its checksum')
    tmp = ZIP.with_suffix('.tmp')
    tmp.write_bytes(blob)
    if not zipfile.is_zipfile(tmp):
        tmp.unlink()
        raise RuntimeError('yt-dlp download is not a zip')
    tmp.replace(ZIP)
    m['version'] = latest
    META.write_text(json.dumps(m))
    log(f'  yt-dlp {latest} downloaded, used from next start')
    return latest
