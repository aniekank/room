"""Samsung TV control: find it on the Wi-Fi, wake it, open a page in its browser.

Works with 2016+ Tizen sets (built on a 2018 UN32M4500).
The first connection pops an "Allow" prompt on the TV; the token is saved so it
only asks once.
"""
import concurrent.futures
import json
import socket
import time
import urllib.request
from pathlib import Path

from paths import DATA

CONFIG = DATA / 'config.json'
TOKEN = DATA / 'tv-token.txt'


def load_config():
    try:
        return json.loads(CONFIG.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(cfg):
    CONFIG.parent.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2))


def mac_ip():
    """The Mac's LAN address (the one the TV can reach), ignoring VPN tunnels."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Route lookup only, nothing is sent. 192.168.x/172.x/10.x all resolve to en0.
        s.connect(('192.168.255.255', 1))
        ip = s.getsockname()[0]
    except OSError:
        ip = '127.0.0.1'
    finally:
        s.close()
    if ip.startswith('10.2.') or ip == '127.0.0.1':  # VPN tunnel (Proton uses 10.2.x)
        import subprocess
        out = subprocess.run(['ipconfig', 'getifaddr', 'en0'], capture_output=True, text=True).stdout.strip()
        ip = out or ip
    return ip


def device_info(host, timeout=2.0):
    """Samsung's REST endpoint: model, name, wifi MAC, power state."""
    with urllib.request.urlopen(f'http://{host}:8001/api/v2/', timeout=timeout) as r:
        return json.load(r)


def find(verbose=True):
    """Scan the Mac's /24 for anything answering Samsung's TV API."""
    base = '.'.join(mac_ip().split('.')[:3])

    def probe(i):
        host = f'{base}.{i}'
        try:
            info = device_info(host, timeout=1.2)
            if 'device' in info:
                return host, info
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(64) as pool:
        hits = [h for h in pool.map(probe, range(1, 255)) if h]
    if verbose:
        print(f'Scanned {base}.1-254: {len(hits)} Samsung TV(s)')
    for host, info in hits:
        d = info['device']
        cfg = load_config()
        cfg.update(tv_host=host, tv_mac=d.get('wifiMac'), tv_model=d.get('modelName'), tv_name=d.get('name'))
        save_config(cfg)
        if verbose:
            print(f"  {host}  {d.get('name')}  model {d.get('modelName')}  mac {d.get('wifiMac')}  power {d.get('PowerState', '?')}")
    return hits


def _tv():
    from samsungtvws import SamsungTVWS
    cfg = load_config()
    host = cfg.get('tv_host')
    if not host:
        raise RuntimeError('No TV saved yet. Turn the TV on and run: room find')
    # First connection waits on a human pressing Allow on the TV, so give it time.
    return SamsungTVWS(host=host, port=8002, token_file=str(TOKEN), name='Room', timeout=8 if TOKEN.exists() else 45)


def wake(mac=None):
    """Wake-on-LAN magic packet. Needed when the TV is fully off, not just in standby."""
    mac = mac or load_config().get('tv_mac')
    if not mac:
        return False
    raw = bytes.fromhex(mac.replace(':', '').replace('-', ''))
    packet = b'\xff' * 6 + raw * 16
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    for port in (9, 7):
        s.sendto(packet, ('255.255.255.255', port))
    s.close()
    return True


def is_on(timeout=2.0):
    host = load_config().get('tv_host')
    if not host:
        return False
    try:
        info = device_info(host, timeout=timeout)
        # 2018+ sets answer in standby too; PowerState tells them apart when present.
        return info.get('device', {}).get('PowerState', 'on') == 'on'
    except Exception:
        return False


def ensure_on(wait=25):
    if not load_config().get('tv_host'):
        return False
    if is_on():
        return True
    wake()
    end = time.time() + wait
    while time.time() < end:
        time.sleep(2)
        if is_on():
            time.sleep(3)  # let the home screen finish loading
            return True
    return False


def open_url(url):
    _tv().open_browser(url)


def key(name):
    _tv().send_key(name)


def pair():
    """Trigger the one-time Allow prompt and keep the token."""
    tv = _tv()
    tv.open()
    print('Paired. Token saved to', TOKEN)
    tv.close()
