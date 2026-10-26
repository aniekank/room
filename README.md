# Room

A Samsung TV as five channels, served from your Mac. Built on a 2018 UN32M4500 (1366×768), so it runs on old Tizen browsers too.

## Get the app

1. Download **Room.dmg** from the [latest release](https://github.com/aniekank/room/releases/latest), open it, and drag **Room** into **Applications**.
2. Open Room from Applications. A little TV appears in the menu bar at the top of the screen (there's no window and no Dock icon).
3. Turn on your Samsung TV, click **Find my TV**, then press **Allow** on the TV when it asks.
4. Click **Connect Your Phone** in the menu and point your phone's camera at the code. That's the remote.

Everything else is in the menu: open a channel on the TV, set the Keys reminder time, pick the World Window cities and the Dig Tube lanes, choose your Movies folder, switch to °C. Room starts by itself when you log in, and it keeps its YouTube search engine (yt-dlp) up to date on its own.

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
  "extra_lanes": {"Italo disco": ["Italo disco 1983 TV", "Italo disco 1985 live"]},
  "movies_folders": ["~/Library/Mobile Documents/com~apple~CloudDocs", "~/Movies"],
  "movies_skip": ["*Udemy*", "/Documents"]
}
```

Your own cities go in `extra_cities`, shaped like the entries in `sources.py`. Lane names are the keys in `dig.py`.

**Personal use only.** Dig Tube and World Window find their videos by searching YouTube with yt-dlp and play them through YouTube's embedded player. That is fine for your own living room, but don't host this for other people or run it as a service.

| # | Channel | What it does |
|---|---------|--------------|
| 1 | **Keys** `/nag` | 20-minute keys session. Today's grip (14 daily sets alternating deep house and R&B, jazz to close the cycle) drawn on a 37-key keyboard, Rhodes sound, play-along loop, a new key every 90s. Logs the session and keeps a streak. |
| 2 | **Dig Tube** `/dig` | Channel-surfs archival clips across 43 lanes (321 searches that walk years and artists, 30 results deep): Soul Train 70s/80s, R&B on TV, quiet storm, neo-soul, go-go, Chicago/Detroit/NYC house, UK acid jazz, Afrobeat, highlife, juju, Ethio-jazz, South Africa, Congo, Jamaica, Brazil, Latin, city pop, Bollywood funk, Anatolian rock, 80s synth pop, prog and krautrock, fusion, library, scores, soft rock, gospel, jazz and hip-hop TV. OK on the TV remote or **Save** on the phone stamps the moment (6s back) into `Dig Saves.md`. |
| 3 | **World Window** `/window` | A muted street cam or walk from Chicago, Lagos, Detroit, London, Johannesburg or Accra, that city's radio, local time and weather, plus one line on its music history. The city changes by weekday (by default Mon Chicago, Tue Lagos, Wed Detroit, Thu London, Fri Johannesburg, Sat Accra, Sun Chicago). |
| 4 | **Movies** `/movies` | Your own video files, by default from the **Movies** folder in iCloud Drive. Add more folders in the menu or with `movies_folders`, subfolders included, and leave things out with `movies_skip` (name patterns; a leading `/` matches only at the top of a folder). Films come first, then each series or collection as its own group, then courses you list in `movies_courses` (one group each, lessons in order): ◀ ▶ jumps between groups. The same file in two places is listed once. Streams from the Mac, so nothing is copied to the TV. Picks up where you stopped. A movie iCloud hasn't downloaded yet says "In iCloud", and OK fetches it and starts it when it lands. The TV's browser plays H.264 and HEVC; for MKV, AVI and MPG files, turn on `"convert_videos": true` and Room writes an MP4 next to each one in the background (video copied when it can be, re-encoded on the Mac's hardware encoder when it can't, audio made stereo AAC), one at a time as disk space allows, then lets both go back to iCloud. Originals are never touched. `bin/room convert status` shows progress. |
| 5 | **FlyBoy[TV]** `/station` | Your own always-on channel: tune in and it's mid-show. Mornings open with **Your Day** (calendar, reminders, Notion tasks, a study card from your notes, files you touched lately, Keys streak, weather), then your series in episode order, **FlyBoy Academy** (the courses) after lunch, a film in prime time, and the **FlyBoyRadio Vault** late at night: an old WMUC show rebuilt from its playlist, or the 2011 recording. **From the Crates** puts a record from the Crate Index on screen and plays it. The Vault and the Crates play their songs from the Mac as music videos (H.264 up to 1080p with AAC, or audio when there's no video), fetched with yt-dlp eight programs ahead, one at a time with a pause between, backing off when YouTube pushes back; the TV's YouTube player refuses most label uploads inside an embed. Up to 2.5 GB when the disk has room, oldest dropped first. yt-dlp uses deno (~/.deno/bin) for YouTube's player scripts. If YouTube keeps asking yt-dlp to prove it isn't a bot, `"youtube_cookies_browser": "chrome"` (or safari, firefox) lets it use your own YouTube sign-in. **Ride With Me** plays your beats (the 2009-2011 recoveries, demo cuts, finished tracks) over the night-drive art and the Tapes cards; the **Queenpin: Era One** montage runs the cast to one of your beats; Your Day plays a beat underneath. **FlyBoy Videos** plays four music videos full screen from the songs the FlyBoyRadio shows played: only real music videos, posted by the artist's own verified or VEVO channel (never a fan edit, a lyric video or a song over a still), picked by views for their age and likes per view, and it learns from you: ▶ past one counts against it, **★ Love this video** on the phone counts for it. A dozen are kept ready on the Mac. **FlyBoy Sports** opens on a desk (the NFL from NFL Intelligence, club football from Club Football Intelligence, World Cup 2026 from World Cup Intelligence, the NBA/NHL/MLB scoreboard, or tennis, boxing, rugby and cricket headlines), the teams it follows first, then the leaders and the models' reads (power rankings, projections, title and relegation odds, the Golden Boot), then three clips fetched to the Mac like the Crates' songs: a player the numbers say is in form, a moment from the sport's whole history (about 1,650 of them, every Super Bowl, NBA Finals, World Series, Stanley Cup, World Cup, European Cup, Wimbledon and Olympics back to the newsreels, chosen a decade at a time), and one of the greats, the revered or the legends in the making; weekend afternoons lean on it, and `"sports_follow"` in settings.json changes who leads each desk. FlyBoy[TV] idents run between programs. Programs coming up from iCloud are downloaded ahead and dropped again after they air. OK shows the guide, ▶ moves on. Queenpin opens the 4pm, 7pm and 11pm blocks; everything is also on demand: ▲ on the TV remote (or the phone's TV tab) opens shelves of segments and promos, your shows and courses (each picks up at its next episode), every film and all 79 Vault shows (fill-in DJs' weeks left out). Something still in iCloud starts as soon as it's down, with a Crates segment covering the wait. Assets live in `iCloud Drive/FlyBoy[TV]`; `bin/room station` refreshes them from `~/Desktop/FlyBoyRadio`. Notion needs your own integration key: `notion_token`, `notion_tasks`, `notion_notes` in settings.json. |

**Phone remote:** `http://<mac-ip>:8788/remote` (run `room status` for the exact address). Add it to the home screen. It switches channels, has a big Save button, lane and city pickers, and wakes the TV when it's off.

**TV remote:** number keys 1 to 5 jump channels and 0 goes home. ◀ ▶ ▲ ▼ and OK do the obvious thing on each channel, and the hint in the corner lists them.

## Commands

```bash
bin/room status        # TV, server, nag time
bin/room show nag      # wake the TV and open a channel (nag|dig|window|movies|home)
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
