"""room: TV channels for the living room.

  room serve              run the server (the launchd agent does this for you)
  room find               find the Samsung TV on the Wi-Fi and remember it
  room pair               one-time "Allow" prompt on the TV
  room show nag|dig|window|home   wake the TV and open a channel
  room nag                the scheduled nudge: opens Keys unless today's 20 minutes are done
  room install [HH:MM]    install to ~/Library/Application Support/Room + launchd (server + daily nag);
                          HH:MM changes the nag time and is remembered in data/settings.json
  room uninstall          remove the launchd agents
  room status             what's saved, what's running
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

import settings  # noqa: E402
from paths import DATA  # noqa: E402

APP = DATA.parent
LA = Path.home() / 'Library' / 'LaunchAgents'
SERVER_LABEL, NAG_LABEL = 'com.task.room.server', 'com.task.room.nag'
PORT = 8788


def _server_up():
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/practice', timeout=2)
        return True
    except Exception:
        return False


def show(channel):
    import tv
    if channel == 'home':
        channel = ''
    if not _server_up():
        print('Server is not running. Start it with: room serve  (or room install)')
        return False
    if not tv.ensure_on():
        print('TV did not answer. Is it on the same Wi-Fi as the Mac? Try: room find')
        return False
    url = f'http://{tv.mac_ip()}:{PORT}/{channel}'
    tv.open_url(url)
    print('Opened', url)
    return True


def notify(title, text):
    subprocess.run(['osascript', '-e', f'display notification {json.dumps(text)} with title {json.dumps(title)} sound name "Glass"'])


def nag():
    try:
        p = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/practice', timeout=3))
    except Exception:
        p = {}
    if p.get('today'):
        print('Keys already done today. No nag.')
        return
    try:
        if show('nag'):
            notify('Keys', 'Twenty minutes. The TV is ready.')
            return
    except Exception as e:
        print('TV route failed:', e)
    # Not home, or the TV is unplugged: put it on the Mac instead.
    notify('Keys', "Twenty minutes. TV's not reachable, so it's on the Mac.")
    url = f'http://127.0.0.1:{PORT}/nag'
    if subprocess.run(['open', '-a', 'Google Chrome', url]).returncode != 0:
        subprocess.run(['open', url])  # no Chrome: the default browser


def _plist(label, args, extra):
    items = ''.join(f'<string>{a}</string>' for a in args)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array>{items}</array>
  <key>WorkingDirectory</key><string>{APP / "app"}</string>
  <key>StandardOutPath</key><string>{APP / "logs" / (label + ".log")}</string>
  <key>StandardErrorPath</key><string>{APP / "logs" / (label + ".log")}</string>
  {extra}
</dict></plist>
'''


def install(at=None):
    """Copy the app out of ~/Desktop (launchd can't read Desktop without a privacy grant),
    give it its own venv, and register the server + the daily nag."""
    if at:
        hh, mm = (int(x) for x in at.split(':'))
        settings.save('nag_time', f'{hh:02d}:{mm:02d}')
    at = settings.get('nag_time')
    hh, mm = (int(x) for x in at.split(':'))
    app = APP / 'app'
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(SRC, app, ignore=shutil.ignore_patterns('.venv', '__pycache__', '*.pyc', '.git', 'Dig Saves.md'))
    (APP / 'logs').mkdir(exist_ok=True)
    venv = APP / 'venv'
    if not venv.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
    has_deps = subprocess.run([str(venv / 'bin' / 'python'), '-c', 'import samsungtvws, yt_dlp'], capture_output=True).returncode == 0
    if not has_deps or '--upgrade' in sys.argv:
        subprocess.run([str(venv / 'bin' / 'pip'), 'install', '-q', '--upgrade', '-r', str(SRC / 'requirements.txt')], check=True)
    py = str(venv / 'bin' / 'python')
    LA.mkdir(exist_ok=True)
    (LA / f'{SERVER_LABEL}.plist').write_text(_plist(SERVER_LABEL, [py, str(app / 'room.py'), 'serve'],
                                                     '<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>'))
    (LA / f'{NAG_LABEL}.plist').write_text(_plist(NAG_LABEL, [py, str(app / 'room.py'), 'nag'],
                                                  f'<key>StartCalendarInterval</key><dict><key>Hour</key><integer>{hh}</integer>'
                                                  f'<key>Minute</key><integer>{mm}</integer></dict>'))
    uid = os.getuid()
    for label in (SERVER_LABEL, NAG_LABEL):
        subprocess.run(['launchctl', 'bootout', f'gui/{uid}/{label}'], capture_output=True)
        # bootout returns before the old process is gone; bootstrap fails with EIO until it is.
        for attempt in range(10):
            r = subprocess.run(['launchctl', 'bootstrap', f'gui/{uid}', str(LA / f'{label}.plist')], capture_output=True, text=True)
            if r.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError(f'launchctl bootstrap {label}: {r.stderr.strip()}')
    # Keep the saves list one click away from the project folder.
    link = SRC / 'Dig Saves.md'
    if not link.is_symlink() and not link.exists():
        link.symlink_to(DATA / 'Dig Saves.md')
    print(f'Installed. Server on :{PORT}, Keys nag daily at {at}.')
    print(f'Phone remote: http://{__import__("tv").mac_ip()}:{PORT}/remote')


def uninstall():
    uid = os.getuid()
    for label in (SERVER_LABEL, NAG_LABEL):
        subprocess.run(['launchctl', 'bootout', f'gui/{uid}/{label}'], capture_output=True)
        (LA / f'{label}.plist').unlink(missing_ok=True)
    print('Agents removed. Data kept in', DATA)


def status():
    import tv
    cfg = tv.load_config()
    print('TV       ', cfg.get('tv_host', 'not found yet'), cfg.get('tv_model', ''), '(paired)' if tv.TOKEN.exists() else '(not paired)')
    print('TV on    ', tv.is_on() if cfg.get('tv_host') else '-')
    print('Server   ', 'up' if _server_up() else 'down', f'http://{tv.mac_ip()}:{PORT}/remote')
    print('Data     ', DATA)
    print('Settings ', settings.FILE if settings.FILE.exists() else 'defaults (see settings.py)')
    nag_plist = LA / f'{NAG_LABEL}.plist'
    if nag_plist.exists():
        import re
        t = nag_plist.read_text()
        h, m = re.findall(r'<integer>(\d+)</integer>', t)[:2]
        print('Nag      ', f'daily {int(h):02d}:{int(m):02d}')


def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'help'
    if cmd == 'serve':
        import server
        server.serve()
    elif cmd == 'find':
        import tv
        tv.find()
    elif cmd == 'pair':
        import tv
        tv.pair()
    elif cmd == 'show':
        show(argv[2] if len(argv) > 2 else 'home')
    elif cmd == 'nag':
        nag()
    elif cmd == 'install':
        install(argv[2] if len(argv) > 2 and ':' in argv[2] else None)
    elif cmd == 'uninstall':
        uninstall()
    elif cmd == 'status':
        status()
    elif cmd == 'warm':
        import sources
        sources.warm()
    else:
        print(__doc__)


if __name__ == '__main__':
    main(sys.argv)
