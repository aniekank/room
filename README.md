# Room

A Samsung TV as three channels, served from your Mac. Built on a 2018 UN32M4500 (1366×768), so it runs on old Tizen browsers too.

## Get the app

1. Download **Room.dmg** from the [latest release](https://github.com/aniekank/room/releases/latest), open it, and drag **Room** into **Applications**.
2. Open Room from Applications. A little TV appears in the menu bar at the top of the screen (there's no window and no Dock icon).
3. Turn on your Samsung TV, click **Find my TV**, then press **Allow** on the TV when it asks.
4. Click **Connect Your Phone** in the menu and point your phone's camera at the code. That's the remote.

Everything else is in the menu: open a channel on the TV, set the Keys reminder time, pick the World Window cities and the Dig Tube lanes, switch to °C. Room starts by itself when you log in, and it keeps its YouTube search engine (yt-dlp) up to date on its own.

**"Room can't be opened" or "Apple could not verify Room":** builds that aren't signed with an Apple Developer ID get this the first time. Open **System Settings → Privacy & Security**, scroll down to the message about Room, click **Open Anyway**, and confirm. You only do this once.

Works on macOS 11 or newer, on Intel and Apple Silicon Macs.

## Run from source

For people who'd rather use Terminal. The app and `bin/room` share the same data, so don't run both servers at once (the app notices and steps aside).

**You need:** a Mac (macOS only: it uses launchd and macOS notifications), Python 3, and a Samsung Tizen smart TV (2016 or newer) on the same Wi-Fi. No Samsung TV? Skip the pairing and use the browser fallback below.

```bash
git clone https://github.com/aniekank/room.git ~/Desktop/Projects/Room
cd ~/Desktop/Projects/Room
bin/setup          # or: bin/setup 07:45  to pick the Keys nag time
```

`bin/setup` makes a `.venv`, installs `samsungtvws` and `yt-dlp` from `requirements.txt`, finds the TV, pairs with it, and installs the background server plus the daily nag.

- **Pairing:** turn the TV on before you run setup. When the TV shows a prompt asking to allow **Room**, press **Allow** with the TV remote. You only do this once. To redo it: `bin/room pair`.
- **Browser fallback:** any TV or phone browser works. Open `http://<mac-ip>:8788` (run `bin/room status` for the exact address). You lose wake-on and the automatic nag on the TV, but every channel plays.
- **The first minutes:** Dig Tube and World Window fill their clip pools in the background, so give them a few minutes after the first install.

**Make it yours** with `~/Library/Application Support/Room/data/settings.json` (all keys optional, defaults in `settings.py`), then run `bin/room install` again:

```json
{
  "nag_time": "07:45",
  "temp_unit": "C",
  "cities": ["london", "lagos", "accra"],
  "day_city": ["london", "lagos", "accra", "london", "lagos", "accra", "london"],
  "dig_lanes": ["Afrobeat", "Highlife", "Jazz on TV"],
  "extra_lanes": {"Italo disco": ["Italo disco 1983 TV", "Italo disco 1985 live"]}
}
```

Your own cities go in `extra_cities`, shaped like the entries in `sources.py`. Lane names are the keys in `dig.py`.

**Personal use only.** Dig Tube and World Window find their videos by searching YouTube with yt-dlp and play them through YouTube's embedded player. That is fine for your own living room, but don't host this for other people or run it as a service.

| # | Channel | What it does |
|---|---------|--------------|
| 1 | **Keys** `/nag` | 20-minute keys session. Today's grip (14 daily sets alternating deep house and R&B, jazz to close the cycle) drawn on a 37-key keyboard, Rhodes sound, play-along loop, a new key every 90s. Logs the session and keeps a streak. |
| 2 | **Dig Tube** `/dig` | Channel-surfs archival clips across 43 lanes (321 searches that walk years and artists, 30 results deep): Soul Train 70s/80s, R&B on TV, quiet storm, neo-soul, go-go, Chicago/Detroit/NYC house, UK acid jazz, Afrobeat, highlife, juju, Ethio-jazz, South Africa, Congo, Jamaica, Brazil, Latin, city pop, Bollywood funk, Anatolian rock, 80s synth pop, prog and krautrock, fusion, library, scores, soft rock, gospel, jazz and hip-hop TV. OK on the TV remote or **Save** on the phone stamps the moment (6s back) into `Dig Saves.md`. |
| 3 | **World Window** `/window` | A muted street cam or walk from Chicago, Lagos, Detroit, London, Johannesburg or Accra, that city's radio, local time and weather, plus one line on its music history. The city changes by weekday (by default Mon Chicago, Tue Lagos, Wed Detroit, Thu London, Fri Johannesburg, Sat Accra, Sun Chicago). |

**Phone remote:** `http://<mac-ip>:8788/remote` (run `room status` for the exact address). Add it to the home screen. It switches channels, has a big Save button, lane and city pickers, and wakes the TV when it's off.

**TV remote:** number keys 1/2/3 jump channels and 0 goes home. ◀ ▶ ▲ ▼ and OK do the obvious thing on each channel, and the hint in the corner lists them.

## Commands

```bash
bin/room status        # TV, server, nag time
bin/room show nag      # wake the TV and open a channel (nag|dig|window|home)
bin/room find          # re-find the TV if its IP changes
bin/room pair          # one-time Allow prompt on the TV
bin/room install       # (re)install after edits or settings changes
bin/room install 19:30 # same, and move the nag to 19:30
bin/room uninstall
```

## How Dig Tube learns (`dig.py`)
- **Favors obscure clips:** weight is roughly 1/log(views)², and anything over 3M views is rationed.
- **No repeats:** nothing you've watched comes back for 21 days. Skip a clip within 45s and it's retired for good.
- **Lane weights:** each Save from a lane raises its share, and quick skips lower it (clamped 0.35x to 4x). `curl localhost:8788/api/dig/stats` shows the weights.
- **Fresh clips:** searches that have never run fill in first (retried every 30 min, so a dropped connection heals itself). After that, the 45 stalest searches re-run each night between 2 and 5am.

## Building the app

```bash
packaging/build.sh
```

That makes `dist/Room.app` and `dist/Room.dmg` with the universal2 Python from python.org, so one build runs on Intel and Apple Silicon. Set `ROOM_SIGN_ID` (a Developer ID Application certificate) and `ROOM_NOTARY_PROFILE` to sign and notarize, which removes the Gatekeeper warning; see the top of `build.sh`. `app.py` is the menu bar app, and `engine.py` downloads newer yt-dlp releases, checks them against yt-dlp's published SHA-256 sums, and loads them in place of the bundled copy.

## How it runs
- `room install` copies the app to `~/Library/Application Support/Room/app` (launchd can't read ~/Desktop without a privacy grant) with its own venv, and registers two LaunchAgents:
  - `com.task.room.server`: always-on server on :8788.
  - `com.task.room.nag`: daily at the `nag_time` setting (19:30 by default). If today's 20 minutes aren't logged, it wakes the TV and opens Keys. If the TV isn't reachable, Keys opens on the Mac instead (Chrome, or your default browser) and you get a notification.
- **Edit here, then `room install` again** to push the changes to the installed copy.
- Data (settings, streak log, saves, caches, TV token) lives in `~/Library/Application Support/Room/data`.
- Sources: radio-browser.info for station streams, YouTube via yt-dlp search (city views cached 6h; the dig pool lives in data/dig.json), and open-meteo for weather. No API keys.

## TV notes
- The TV opens pages in its built-in browser. The pages stick to ES2015, flexbox and no CSS grid so the 2018 Tizen engine can run them.
- First connection needs **Allow** on the TV. If it says unauthorized: TV Settings → General → External Device Manager → Device Connect Manager → Device List, set **Room** to Allow (or delete it and pair again).
- Wake from fully off uses Wake-on-LAN. If `room show` can't wake it, turn on Settings → General → Network → Expert Settings → **Power On with Mobile**.
