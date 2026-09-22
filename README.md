# Broadcast Channel POC

A linear TV channel: one continuously-encoded live HLS stream, and TVs that
tune it the way a television tunes a broadcast.

There is no per-TV schedule, no playlist arithmetic on the client, no
position reporting, and no coordination between TVs. What is on air is
decided in one place - the channel engine - and every screen just plays it.

```
content/*.mp4                      3 source clips
      |
      v
  ffmpeg  (-re -stream_loop -1)    loops them in realtime, forever
      |
      v
  public/channel/live.m3u8         rolling 6-segment live manifest
  public/channel/seg_*.ts          + EXT-X-PROGRAM-DATE-TIME
      |
      | plain HTTP GET (no session, no handshake)
      |
  +---+--------+--------+
  |            |        |
 TV 1         TV 2     TV 3        each just plays the live edge
```

---

## Layout

```
pocvideo/
├── channel-server/          Node.js, zero dependencies
│   ├── server.js            origin + pairing API + admin dashboard
│   ├── engine.js            ffmpeg supervisor (the channel itself)
│   ├── store.js             device registry
│   ├── fetch-content.sh     downloads + normalises the clips
│   ├── channels.json        channel definitions
│   ├── content/             source media + concat list
│   └── public/
│       ├── admin.html       operator dashboard
│       └── channel/         live manifest + segments (generated)
│
└── tv-app/                  LightningJS / Blits
    ├── src/pages/Pairing.js first boot only
    ├── src/pages/Player.js  the entire client
    ├── src/utils/device.js  identity, credentials, server clock
    └── android/             Capacitor wrapper
```

---

## Running it

Generate the test content once:

```sh
cd channel-server && ./fetch-content.sh
```

Start the channel (this also starts ffmpeg):

```sh
cd channel-server && node server.js
```

Dashboard at `http://<your-ip>:4000/`, channel at
`http://<your-ip>:4000/channel/live.m3u8`.

Then the TV app:

```sh
cd tv-app && npm install && npm run dev
```

Android TV:

```sh
cd tv-app && npm run android:apk
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
adb shell monkey -p com.pocvideo.channeltv -c android.intent.category.LEANBACK_LAUNCHER 1
```

---

## How the channel is made

The channel is **ffmpeg**, supervised by Node. Node never touches video
data - it starts the process, watches it, and serves the directory ffmpeg
writes into.

```
ffmpeg -re -stream_loop -1 -f concat -safe 0 -i content/playlist.txt \
  -c:v libx264 -g 50 -c:a aac \
  -f hls -hls_time 4 -hls_list_size 6 \
  -hls_flags delete_segments+append_list+program_date_time \
  public/channel/live.m3u8
```

| flag | why it matters |
|---|---|
| `-re` | paces the read at realtime; without it ffmpeg races through the files and nothing is "live" |
| `-stream_loop -1` | loops the concatenated playlist forever |
| `-hls_time 4` | 4s segments; `-g 50` puts a keyframe every 2s so segments always split cleanly |
| `-hls_list_size 6` | rolling ~24s window |
| `delete_segments` | keeps the disk from filling over days of uptime |
| `append_list` | survives a restart without resetting the media sequence |
| `program_date_time` | tags every segment with wall-clock time - this is what makes frame-accurate sync possible |

Re-encoding rather than `-c copy` is deliberate: looping a concat with
`-c copy` produces DTS discontinuities at every wrap. Once sources are
known-identical, `-c copy` is much cheaper and worth switching to.

---

## Why TVs stay in sync

Two mechanisms, and the second is the one people miss.

**Same channel.** Every TV requests the same manifest. None of them owns a
schedule, so none of them can disagree about what is on.

**Same frame.** This does *not* come for free. Each player picks its own
start point near the live edge, and once two TVs are apart nothing pulls
them back - drift in live HLS has no restoring force.

So the player holds a fixed latency behind a shared clock:

```
target   = serverNow() - 12000ms
drift    = hls.playingDate - target        (playingDate comes from PDT)

|drift| <= 300ms     leave it alone
|drift| <= 5000ms    playbackRate 0.98 / 1.02
|drift|  > 5000ms    seek (clamped to the seekable range)
```

`serverNow()` is round-trip corrected: `t0` is recorded *before* the
request, and the offset is taken from the midpoint over several samples,
keeping the lowest-latency one. Measuring after the response lands bakes
in half the round trip and biases every TV differently.

Observed on the Android TV emulator, converging from a cold start:

```
drift -2364ms  rate 1.02x
drift -1740ms  rate 1.02x
drift  -601ms  rate 1.02x
drift  -287ms  rate 1.00x   <- inside deadband, correction released
```

The -2364 to -1740 step is 624ms over ~31s of channel time, which is
exactly the 2% that 1.02x predicts.

---

## Channels and playlists

A channel is a directory of clips plus one ffmpeg process. Three exist:

| Channel | Content |
|---|---|
| `cartoons` | Big Buck Bunny, Sintel, Elephants Dream (excerpt 1) |
| `shorts` | the same three films, excerpt 2 |
| `classics` | the same three films, excerpt 3 |

All are Blender Foundation open movies (CC-BY) fetched by
`./fetch-content.sh`, which pulls 60-second excerpts rather than whole
films - `-ss` before `-i` makes ffmpeg seek with HTTP range requests.

```
content/cartoons/*.mp4  +  playlist.txt   →   ffmpeg   →   public/channels/cartoons/live.m3u8
content/shorts/*.mp4    +  playlist.txt   →   ffmpeg   →   public/channels/shorts/live.m3u8
content/classics/*.mp4  +  playlist.txt   →   ffmpeg   →   public/channels/classics/live.m3u8
```

Adding a channel means adding a directory of clips, a `playlist.txt`, and
an entry in `channels.json`.

**Cost scales with channels, not TVs.** Each channel is one encoder
process. A thousand TVs watching one channel is exactly the same work as
one TV watching it - they are all just fetching the same static segments.
Adding a fourth channel costs a fourth encoder.

Every clip in a channel must share identical codec, resolution, frame
rate and audio layout, because the concat demuxer joins them without
re-negotiating. `fetch-content.sh` normalises everything to 1280x720 /
25fps / AAC 48kHz stereo for exactly this reason.

---

## Pairing

A TV is an appliance. It is authorised once by an operator and never asks
anyone for anything again - no login, no password typed with a remote.

```
first boot          TV shows a 6-character code
                    operator enters it in the dashboard
                    TV receives { token, channelUrl }, stores it
                    plays

every boot after    TV finds its token -> plays
                    zero human interaction
```

This matters most after a power cut. With a login screen, somebody walks
to every TV in the building. With pairing, they all come back on their own.

Codes use an alphabet with no `O/0` or `I/1`, because they get read off a
screen across a room.

---

## Endpoints

| | |
|---|---|
| `GET /channels/<id>/live.m3u8` | a channel. Anonymous, cacheable, no session |
| `POST /api/device/pair/start` | TV asks for a code |
| `GET /api/device/pair/status` | TV polls until claimed |
| `GET /api/device/config` | per-boot config + heartbeat (Bearer token) |
| `POST /api/admin/claim` | operator authorises a device onto a channel |
| `GET /api/admin/devices` | fleet list |
| `GET /api/admin/channels` | channel list + health |
| `POST /api/admin/device/channel` | move a TV to another channel |
| `POST /api/admin/reload` | restart one engine after a playlist change |
| `GET /api/status` | all channel health + server time |

Cache headers matter more than they look: the manifest is `no-store`,
segments are `immutable, max-age=31536000`. A CDN caching the manifest
stalls every TV at once and looks exactly like an encoder failure.

---

## Platform portability

The TV app is LightningJS (Blits) and builds to a plain web bundle, which
is what Tizen and webOS package directly. Nothing platform-specific lives
in the player: it is `<video>` + hls.js + a drift loop.

Android-specific pieces, all isolated:

- `src/utils/device.js` - the `10.0.2.2` emulator fallback in `getApiBase()`
- `android/` - the Capacitor wrapper
- `MainActivity.java` - keep-screen-on and autoplay-without-gesture

Porting to Tizen or webOS means adding a packaging directory and a
platform branch in `getApiBase()`. The player is untouched.

Two Blits details worth knowing, both of which cost real debugging time:

**Dynamic bindings need the `:` prefix.** `content="$code"` renders the
initial value and never updates; `:content="$code"` is reactive.

**Nothing above the video may be painted opaque.** The Lightning canvas is
layered above the `<video>` element (`#app` is `z-index: 2`) so overlays
can be drawn over the picture. That means any opaque `color` on the
application root or on a page root covers the video completely - and
because overlay text still renders on top, it looks exactly like video
playback has failed. It hasn't: `videoWidth`, `currentTime` and
`hls.playingDate` all keep advancing behind the paint.

Only screens that genuinely need a solid background (Pairing) set a root
colour. `App.js` and `Player.js` must stay transparent.

---

## Known limitations

This is a POC. Before production:

- **Playlist changes restart ffmpeg.** The concat demuxer reads its list
  once, so changing content is a real cut on air. A production channel
  assembler writes the manifest itself to avoid this.
- **No auth on the admin API.** Anyone who can reach the server can pair a
  device or reload the channel.
- **Device registry is a JSON file.** Cannot be shared across instances,
  so no horizontal scaling.
- **Single origin, no CDN.** Every TV pulls segments from one Node process.
- **No monitoring beyond the dashboard.** The engine detects a wedged
  ffmpeg by watching segment production, but nothing pages anyone.
- **Audio is muted** in `Player.js`. `MainActivity` already disables the
  gesture requirement, so removing that line should be all it takes.
