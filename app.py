"""Room.app: the menu bar version for people who don't use Terminal.

It runs the same server in-process, fires the Keys nag itself (no launchd agent),
walks through finding and pairing the TV, and turns settings.json into menus.
`bin/room` keeps working for anyone who prefers the command line.
"""
import fcntl
import json
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

FROZEN = getattr(sys, 'frozen', False)
HERE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
sys.path.insert(0, str(HERE))

from paths import DATA  # noqa: E402

LOGS = DATA.parent / 'logs'
LOGS.mkdir(exist_ok=True)
if FROZEN:  # Finder gives an app no terminal; keep the server's output somewhere useful
    sys.stdout = sys.stderr = open(LOGS / 'app.log', 'a', buffering=1)
    import certifi  # the bundled Python has no system certificates of its own
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())

import engine  # noqa: E402
engine.activate()  # before anything imports yt_dlp

import rumps  # noqa: E402

import dig  # noqa: E402
import movies  # noqa: E402
import room  # noqa: E402
import settings  # noqa: E402
import sources  # noqa: E402
import tv  # noqa: E402

PORT = room.PORT
STATE = DATA / 'app_state.json'
LABEL = 'com.aniekank.room'
LOGIN_PLIST = room.LA / f'{LABEL}.plist'
CLI_NAG = room.LA / f'{room.NAG_LABEL}.plist'
HELP_URL = 'https://github.com/aniekank/room#readme'
NAG_TIMES = ['07:00', '08:00', '12:00', '17:00', '18:00', '19:00', '19:30', '20:00', '21:00']
CHANNELS = [('Home', ''), ('Keys', 'nag'), ('Dig Tube', 'dig'), ('World Window', 'window'), ('Movies', 'movies')]


def state():
    try:
        return json.loads(STATE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(**kw):
    s = state()
    s.update(kw)
    STATE.write_text(json.dumps(s, indent=2))


def bundle_path():
    """/Applications/Room.app when frozen, else None."""
    return Path(sys.executable).resolve().parents[2] if FROZEN else None


def open_url(url):
    subprocess.run(['open', url])


def set_login(on):
    """A LaunchAgent that opens the app at login (launchd, so no permission prompt)."""
    if not on:
        LOGIN_PLIST.unlink(missing_ok=True)
        return
    app = bundle_path()
    if not app:
        return
    room.LA.mkdir(exist_ok=True)
    LOGIN_PLIST.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array><string>/usr/bin/open</string><string>-a</string><string>{app}</string></array>
  <key>RunAtLoad</key><true/>
</dict></plist>
''')


class RoomApp(rumps.App):
    def __init__(self):
        icon = HERE / 'menubar.png'
        super().__init__('Room', icon=str(icon) if icon.exists() else None, template=True,
                         title=None if icon.exists() else 'Room', quit_button=None)
        self.ui = queue.Queue()  # alerts must run on the main thread
        self.external = room._server_up()  # bin/room install already runs a server
        self.status_item = rumps.MenuItem('Starting…')
        self.tv_item = rumps.MenuItem('TV: …')
        self.nag_menu = rumps.MenuItem('Keys Reminder')
        self.city_menu = rumps.MenuItem('World Window Cities')
        self.lane_menu = rumps.MenuItem('Dig Tube Lanes')
        self.temp_menu = rumps.MenuItem('Temperature')
        self.movies_menu = rumps.MenuItem('Movies Folder')
        self.login_item = rumps.MenuItem('Open at Login', callback=self.toggle_login)
        self.engine_item = rumps.MenuItem('Update YouTube Search', callback=self.update_engine)
        on_tv = rumps.MenuItem('Open on TV')
        for name, ch in CHANNELS:
            on_tv.add(rumps.MenuItem(name, callback=lambda _, ch=ch: self.show(ch)))
        self.menu = [
            self.status_item, self.tv_item, None,
            on_tv,
            rumps.MenuItem('Open on This Mac', callback=lambda _: open_url(f'http://127.0.0.1:{PORT}/')),
            rumps.MenuItem('Connect Your Phone…', callback=lambda _: open_url(f'http://127.0.0.1:{PORT}/connect')),
            None,
            self.nag_menu, self.city_menu, self.lane_menu, self.temp_menu, self.movies_menu,
            None,
            rumps.MenuItem('Set Up TV…', callback=self.setup_tv),
            self.login_item, self.engine_item,
            rumps.MenuItem('Help', callback=lambda _: open_url(HELP_URL)),
            None,
            rumps.MenuItem('Quit Room', callback=lambda _: rumps.quit_application()),
        ]
        self.build_settings_menus()
        if not self.external:
            threading.Thread(target=self.run_server, daemon=True).start()
        threading.Thread(target=self.background, daemon=True).start()
        rumps.Timer(self.drain_ui, 0.3).start()
        rumps.Timer(self.refresh, 5).start()
        rumps.Timer(self.check_nag, 30).start()
        self.later(self.first_run)

    # ------------------------------------------------------------ plumbing

    def later(self, fn):
        self.ui.put(fn)

    def drain_ui(self, _):
        while not self.ui.empty():
            try:
                self.ui.get_nowait()()
            except Exception as e:
                print('ui error:', e, flush=True)

    def run_server(self):
        try:
            import server
            server.serve()
        except OSError as e:
            print('server:', e, flush=True)
            self.later(lambda: rumps.alert('Room could not start',
                                           f'Something else is using port {PORT}. Quit it, then open Room again.'))

    def background(self):
        time.sleep(60)
        while True:
            try:
                engine.update(log=lambda m: print(m, flush=True))
            except Exception as e:
                print('yt-dlp update check failed:', e, flush=True)
            time.sleep(6 * 3600)

    def refresh(self, _=None):
        up = room._server_up()
        self.status_item.title = ('Room is running' if up else 'Room is starting…') + (' (bin/room)' if self.external else '')
        cfg = tv.load_config()
        if not cfg.get('tv_host'):
            self.tv_item.title = 'TV: not set up yet'
        else:
            self.tv_item.title = f"TV: {cfg.get('tv_name') or cfg.get('tv_model') or cfg['tv_host']}" + \
                ('' if tv.TOKEN.exists() else ' (not paired)')
        self.login_item.state = int(LOGIN_PLIST.exists())
        self.engine_item.title = f'Update YouTube Search (yt-dlp {engine.version()})'

    # ------------------------------------------------------------ first run

    def first_run(self):
        self.refresh()
        app = bundle_path()
        if app and not str(app).startswith('/Applications/') and not state().get('warned_location'):
            save_state(warned_location=True)
            if rumps.alert('Move Room to Applications',
                           'Room works best from your Applications folder. Quit Room, drag it into Applications, '
                           'and open it from there.', ok='Show Room in Finder', cancel='Not now'):
                subprocess.run(['open', '-R', str(app)])
        if state().get('welcomed'):
            return
        save_state(welcomed=True)
        if FROZEN:
            set_login(True)
        if rumps.alert('Room is in your menu bar',
                       'Look for the little TV at the top of your screen. Let\'s find your Samsung TV first. '
                       'Turn it on and make sure it\'s on the same Wi-Fi as this Mac.',
                       ok='Find my TV', cancel='Later'):
            self.setup_tv()

    # ------------------------------------------------------------ TV

    def setup_tv(self, _=None):
        self.tv_item.title = 'TV: looking…'

        def work():
            try:
                hits = tv.find(verbose=False)
            except Exception as e:
                hits, err = [], str(e)
            else:
                err = ''
            self.later(lambda: self.found(hits, err))
        threading.Thread(target=work, daemon=True).start()

    def found(self, hits, err):
        self.refresh()
        addr = f'http://{tv.mac_ip()}:{PORT}'
        if not hits:
            if rumps.alert('No Samsung TV found',
                           'Check that the TV is on and on the same Wi-Fi as this Mac, then try Set Up TV again.\n\n'
                           f'Any other TV works too: open {addr} in its web browser.' + (f'\n\n({err})' if err else ''),
                           ok='Copy that address', cancel='OK'):
                subprocess.run(['pbcopy'], input=addr.encode())
            return
        name = hits[-1][1]['device'].get('name') or 'your TV'
        if not rumps.alert(f'Found {name}',
                           'Next, your TV will ask whether to allow "Room". Press Allow with your TV remote. '
                           'You only have to do this once.', ok='Pair now', cancel='Later'):
            return
        self.tv_item.title = 'TV: waiting for Allow on the TV…'

        def work():
            try:
                tv.pair()
                tv.open_url(f'{addr}/')
                msg = ('Paired', 'Room just opened on your TV. Next, try Connect Your Phone in the menu.')
            except Exception as e:
                msg = ('Pairing did not finish', 'Make sure you pressed Allow on the TV, then try Set Up TV again. '
                       'If the TV never asked, go to TV Settings, General, External Device Manager, Device Connect Manager '
                       f'and set Room to Allow.\n\n({e})')
            self.later(lambda: (self.refresh(), rumps.alert(*msg)))
        threading.Thread(target=work, daemon=True).start()

    def show(self, ch):
        def work():
            ok = False
            try:
                ok = room.show(ch or 'home')
            except Exception as e:
                print('show:', e, flush=True)
            if not ok:
                self.later(lambda: rumps.alert('Could not reach the TV',
                                               'Is it plugged in and on the same Wi-Fi? Try Set Up TV in the menu.'))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ Keys nag

    def check_nag(self, _):
        at = settings.get('nag_time')
        if not at or at == 'off' or CLI_NAG.exists():  # bin/room's launchd agent handles it
            return
        now = datetime.now()
        hh, mm = (int(x) for x in at.split(':'))
        due = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        today = now.date().isoformat()
        # A Mac that wakes up late in the evening shouldn't nag at midnight.
        if due <= now < due + timedelta(hours=3) and state().get('nagged') != today:
            save_state(nagged=today)
            threading.Thread(target=room.nag, daemon=True).start()

    # ------------------------------------------------------------ settings menus

    def build_settings_menus(self):
        for m in (self.nag_menu, self.city_menu, self.lane_menu, self.temp_menu, self.movies_menu):
            if m._menu is not None:
                m.clear()
        cur = settings.get('nag_time') or 'off'
        self.nag_menu.add(self._check('Off', cur == 'off', lambda _: self.set_nag('off')))
        self.nag_menu.add(None)
        times = NAG_TIMES if cur in NAG_TIMES or cur == 'off' else sorted(NAG_TIMES + [cur])
        for t in times:
            self.nag_menu.add(self._check(self._clock(t), cur == t, lambda _, t=t: self.set_nag(t)))
        self.nag_menu.add(None)
        self.nag_menu.add(rumps.MenuItem('Other Time…', callback=self.other_nag_time))

        on = {c['id'] for c in sources.CITIES}
        for c in sources.BUILTIN_CITIES + settings.get('extra_cities'):
            self.city_menu.add(self._check(c['name'], c['id'] in on, lambda _, i=c['id']: self.toggle_city(i)))

        lanes = set(dig.LANES)
        builtin = list(dig.BUILTIN_LANES)
        self.lane_menu.add(self._check('All Lanes', all(l in lanes for l in builtin), lambda _: self.set_lanes(None)))
        self.lane_menu.add(None)
        for l in builtin + list(settings.get('extra_lanes')):
            self.lane_menu.add(self._check(l, l in lanes, lambda _, l=l: self.toggle_lane(l)))

        unit = 'C' if str(settings.get('temp_unit')).upper().startswith('C') else 'F'
        self.temp_menu.add(self._check('Fahrenheit (°F)', unit == 'F', lambda _: self.set_setting('temp_unit', 'F')))
        self.temp_menu.add(self._check('Celsius (°C)', unit == 'C', lambda _: self.set_setting('temp_unit', 'C')))
        self.movies_menu.add(rumps.MenuItem(f'Playing from {movies.label(movies.folder())}'))  # titles are menu keys, so not the bare path
        self.movies_menu.add(None)
        self.movies_menu.add(rumps.MenuItem('Choose Folder…', callback=self.choose_movies))
        self.movies_menu.add(self._check('iCloud Drive/Movies', movies.folder() == movies.DEFAULT,
                                         lambda _: self.set_setting('movies_folder', None)))
        self.movies_menu.add(rumps.MenuItem('Show in Finder', callback=lambda _: self.show_movies()))

    @staticmethod
    def _check(title, on, cb):
        item = rumps.MenuItem(title, callback=cb)
        item.state = int(on)
        return item

    @staticmethod
    def _clock(t):
        return datetime.strptime(t, '%H:%M').strftime('%-I:%M %p')

    def set_setting(self, key, value):
        settings.save(key, value)
        sources.reload()
        dig.reload()
        self.build_settings_menus()
        if self.external and key not in ('nag_time', 'movies_folder'):  # both are read live
            rumps.alert('Saved', 'Room is running from bin/room, so run "bin/room install" to apply this.')

    def set_nag(self, t):
        self.set_setting('nag_time', t)
        if t != 'off' and datetime.now().strftime('%H:%M') >= t:
            save_state(nagged=datetime.now().date().isoformat())  # a new time today shouldn't fire right away
        if CLI_NAG.exists():
            rumps.alert('Saved', 'Your Keys reminder is run by bin/room. Run "bin/room install" to apply the new time.')

    def other_nag_time(self, _):
        cur = settings.get('nag_time')
        r = rumps.Window('Remind me at (24-hour time, like 19:30):', 'Keys Reminder',
                         default_text='' if cur == 'off' else cur, ok='Save', cancel='Cancel', dimensions=(160, 24)).run()
        if not r.clicked:
            return
        try:
            t = datetime.strptime(r.text.strip(), '%H:%M').strftime('%H:%M')
        except ValueError:
            rumps.alert('That time didn\'t work', 'Use 24-hour time, like 07:45 or 19:30.')
            return
        self.set_nag(t)

    def choose_movies(self, _):
        start = movies.folder() if movies.folder().is_dir() else movies.ICLOUD
        r = subprocess.run(['osascript', '-e', f'POSIX path of (choose folder with prompt "Pick the folder with your movies" '
                            f'default location (POSIX file {json.dumps(str(start))}))'], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():  # Cancel exits non-zero
            p = Path(r.stdout.strip())
            self.set_setting('movies_folder', None if p == movies.DEFAULT else str(p).replace(str(Path.home()), '~', 1))

    def show_movies(self):
        f = movies.folder()
        if not f.is_dir():
            if not rumps.alert('No Movies folder yet', f'Make {movies.label(f)} now?', ok='Make It', cancel='Cancel'):
                return
            f.mkdir(parents=True)
        subprocess.run(['open', str(f)])

    def toggle_city(self, cid):
        builtin = [c['id'] for c in sources.BUILTIN_CITIES]
        if cid not in builtin:
            return rumps.alert('Your own cities', 'Cities you added in settings.json stay on. Remove them there.')
        on = [c['id'] for c in sources.CITIES if c['id'] in builtin]
        if cid in on:
            if len(sources.CITIES) == 1:
                return rumps.alert('World Window needs at least one city.')
            on.remove(cid)
        else:
            on.append(cid)
        self.set_setting('cities', None if len(on) == len(builtin) else [i for i in builtin if i in on])

    def toggle_lane(self, lane):
        builtin = list(dig.BUILTIN_LANES)
        if lane not in builtin:
            return rumps.alert('Your own lanes', 'Lanes you added in settings.json stay on. Remove them there.')
        on = [l for l in builtin if l in dig.LANES]
        if lane in on:
            if len(on) == 1:
                return rumps.alert('Dig Tube needs at least one lane.')
            on.remove(lane)
        else:
            on.append(lane)
        self.set_lanes(None if len(on) == len(builtin) else [l for l in builtin if l in on])

    def set_lanes(self, lanes):
        self.set_setting('dig_lanes', lanes)

    # ------------------------------------------------------------ login + updates

    def toggle_login(self, _):
        set_login(not LOGIN_PLIST.exists())
        self.refresh()

    def update_engine(self, _):
        self.engine_item.title = 'Checking for a newer yt-dlp…'

        def work():
            try:
                new = engine.update(force=True)
            except Exception as e:
                new, err = None, str(e)
            else:
                err = ''
            self.later(lambda: self.engine_done(new, err))
        threading.Thread(target=work, daemon=True).start()

    def engine_done(self, new, err):
        self.refresh()
        if err:
            return rumps.alert('Could not update', err)
        if not new:
            return rumps.alert('Up to date', f'yt-dlp {engine.version()} is the newest.')
        if rumps.alert('Updated', f'yt-dlp {new} is ready. Restart Room to use it.', ok='Restart Now', cancel='Later'):
            self.restart()

    def restart(self):
        app = bundle_path()
        if app:
            subprocess.Popen(['/bin/sh', '-c', f'sleep 2; open "{app}"'])
        rumps.quit_application()


def main():
    lock = open(DATA / 'app.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:  # already running: just show the phone page so the double-click does something
        open_url(f'http://127.0.0.1:{PORT}/connect')
        return
    if FROZEN and LOGIN_PLIST.exists():
        set_login(True)  # keep the login item pointing at wherever the app lives now
    print(f'Room {datetime.now():%Y-%m-%d %H:%M} starting, yt-dlp {engine.version()}', flush=True)
    RoomApp().run()


if __name__ == '__main__':
    main()
