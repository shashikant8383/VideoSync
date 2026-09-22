'use strict'

/*
 * Channel engine.
 *
 * One instance == one channel == one long-lived ffmpeg process looping
 * that channel's playlist into a rolling live HLS manifest.
 *
 * Content for channel "cartoons" lives in content/cartoons/ with a
 * playlist.txt concat list, and is published at
 * public/channels/cartoons/live.m3u8. Everything downstream - origin, CDN,
 * every TV - is a plain HTTP consumer of that manifest. No TV ever talks
 * back, and nothing but this process decides what is on air.
 *
 * Two things here matter more than they look:
 *
 *   program_date_time  tags every segment with a wall-clock time. Without
 *                      it TVs land wherever their player feels like near
 *                      the live edge and stay that far apart forever. With
 *                      it a client can hold a precise offset behind live.
 *
 *   supervision        ffmpeg dies. Bad source file, disk hiccup, OOM. A
 *                      channel without a restart policy is a channel that
 *                      goes dark at 3am. Liveness of the process is not
 *                      the signal that matters either - a wedged ffmpeg
 *                      stays alive while producing nothing, so this
 *                      watches segment production instead.
 */

const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

const SEGMENT_SECONDS = 4
const WINDOW_SEGMENTS = 6

// If the manifest stops advancing for this long, ffmpeg is wedged even if
// the process is still up. Kill it and let the restart policy take over.
const STALL_TIMEOUT_MS = 20000

const RESTART_DELAY_MS = 2000
const RESTART_DELAY_MAX_MS = 30000

class ChannelEngine {
  constructor({ id, name }) {
    this.id = id
    this.name = name || id

    this.contentDir = path.join(__dirname, 'content', id)
    this.outputDir = path.join(__dirname, 'public', 'channels', id)
    this.playlistFile = path.join(this.contentDir, 'playlist.txt')
    this.manifest = path.join(this.outputDir, 'live.m3u8')

    this.process = null
    this.stopping = false
    this.restartDelay = RESTART_DELAY_MS
    this.restartCount = 0
    this.startedAt = null
    this.lastManifestMtime = 0
    this.lastManifestChangeAt = 0
    this.stallTimer = null
    this.lastError = null
  }

  start() {
    this.stopping = false
    this.spawnFfmpeg()
    this.watchForStalls()
  }

  buildArgs() {
    return [
      '-hide_banner',
      '-loglevel', 'warning',

      // Pace the read at realtime. Without this ffmpeg races through the
      // files as fast as it can and the "live" stream is anything but.
      '-re',

      // Loop the concatenated playlist forever.
      '-stream_loop', '-1',
      '-f', 'concat',
      '-safe', '0',
      '-fflags', '+genpts',
      '-i', this.playlistFile,

      // Re-encode rather than -c copy. Copying is cheaper and is the right
      // call once sources are known-identical, but looping a concat with
      // -c copy produces DTS discontinuities at every wrap that some
      // players show as a stutter. Encoding regenerates clean timestamps.
      '-c:v', 'libx264',
      '-preset', 'veryfast',
      '-profile:v', 'main',
      '-pix_fmt', 'yuv420p',
      '-r', '25',

      // Keyframe every 2s so segments can always split on a boundary.
      '-g', '50',
      '-keyint_min', '50',
      '-sc_threshold', '0',

      '-b:v', '2000k',
      '-maxrate', '2000k',
      '-bufsize', '4000k',

      '-c:a', 'aac',
      '-b:a', '128k',
      '-ar', '48000',
      '-ac', '2',

      '-f', 'hls',
      '-hls_time', String(SEGMENT_SECONDS),
      '-hls_list_size', String(WINDOW_SEGMENTS),

      // delete_segments   keeps the disk from filling over days of uptime
      // append_list       survives a restart without resetting the sequence
      // program_date_time emits EXT-X-PROGRAM-DATE-TIME (see above)
      // independent_segs  lets a client start on any segment
      '-hls_flags', 'delete_segments+append_list+program_date_time+independent_segments',

      '-hls_segment_type', 'mpegts',
      '-hls_segment_filename', path.join(this.outputDir, 'seg_%06d.ts'),

      this.manifest,
    ]
  }

  spawnFfmpeg() {
    if (this.stopping) {
      return
    }

    fs.mkdirSync(this.outputDir, { recursive: true })

    if (!fs.existsSync(this.playlistFile)) {
      this.lastError = `No playlist at ${this.playlistFile} - run ./fetch-content.sh first`
      console.error(`[${this.id}] ${this.lastError}`)
      this.scheduleRestart()
      return
    }

    console.log(`[${this.id}] starting ffmpeg`)

    this.process = spawn('ffmpeg', this.buildArgs(), {
      cwd: this.contentDir,
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    this.startedAt = Date.now()
    this.lastManifestChangeAt = Date.now()

    this.process.stderr.on('data', (chunk) => {
      const text = chunk.toString().trim()

      if (!text) {
        return
      }

      this.lastError = text.split('\n').slice(-1)[0]
      console.error(`[${this.id}/ffmpeg] ${text}`)
    })

    this.process.on('exit', (code, signal) => {
      const uptime = Date.now() - this.startedAt

      console.error(
        `[${this.id}] ffmpeg exited code=${code} signal=${signal} after ${Math.round(uptime / 1000)}s`
      )

      this.process = null

      // A process that stayed up a while was healthy; reset the backoff so
      // a single transient failure doesn't leave us waiting 30s.
      if (uptime > 60000) {
        this.restartDelay = RESTART_DELAY_MS
      }

      this.scheduleRestart()
    })

    this.process.on('error', (error) => {
      this.lastError = error.message
      console.error(`[${this.id}] failed to spawn ffmpeg:`, error.message)
    })
  }

  scheduleRestart() {
    if (this.stopping) {
      return
    }

    this.restartCount += 1

    const delay = this.restartDelay

    console.log(`[${this.id}] restarting in ${delay}ms (restart #${this.restartCount})`)

    this.restartDelay = Math.min(this.restartDelay * 2, RESTART_DELAY_MAX_MS)

    setTimeout(() => this.spawnFfmpeg(), delay)
  }

  watchForStalls() {
    this.stallTimer = setInterval(() => {
      if (this.stopping || !this.process) {
        return
      }

      let mtime = 0

      try {
        mtime = fs.statSync(this.manifest).mtimeMs
      } catch {
        // Manifest not written yet - startup grace period covers this.
      }

      if (mtime > this.lastManifestMtime) {
        this.lastManifestMtime = mtime
        this.lastManifestChangeAt = Date.now()
        return
      }

      const since = Date.now() - this.lastManifestChangeAt

      if (since > STALL_TIMEOUT_MS) {
        console.error(
          `[${this.id}] manifest has not advanced in ${Math.round(since / 1000)}s - killing wedged ffmpeg`
        )

        this.lastManifestChangeAt = Date.now()

        try {
          this.process.kill('SIGKILL')
        } catch (error) {
          console.error(`[${this.id}] kill failed:`, error.message)
        }
      }
    }, 5000)
  }

  /*
   * The concat demuxer reads its list once at startup and never re-reads
   * it, so a playlist change means a new ffmpeg. That is a real cut on
   * air - every TV on this channel rebuffers for a segment or two. A
   * production channel assembler writes the manifest itself precisely to
   * avoid this; here it is an explicit, visible operation.
   */
  reload(reason) {
    console.log(`[${this.id}] reload requested: ${reason}`)

    if (this.process) {
      this.process.kill('SIGTERM')
    }
  }

  stop() {
    this.stopping = true

    if (this.stallTimer) {
      clearInterval(this.stallTimer)
      this.stallTimer = null
    }

    if (this.process) {
      this.process.kill('SIGTERM')
      this.process = null
    }
  }

  status() {
    let manifestAge = null
    let segmentCount = 0

    try {
      manifestAge = Math.round((Date.now() - fs.statSync(this.manifest).mtimeMs) / 1000)
    } catch {
      manifestAge = null
    }

    try {
      segmentCount = fs.readdirSync(this.outputDir).filter((f) => f.endsWith('.ts')).length
    } catch {
      segmentCount = 0
    }

    return {
      id: this.id,
      name: this.name,
      running: Boolean(this.process),
      onAir: manifestAge !== null && manifestAge < 15,
      uptimeSeconds: this.startedAt ? Math.round((Date.now() - this.startedAt) / 1000) : 0,
      restartCount: this.restartCount,
      manifestAgeSeconds: manifestAge,
      segmentsOnDisk: segmentCount,
      videos: this.listVideos(),
      lastError: this.lastError,
    }
  }

  listVideos() {
    try {
      return fs
        .readFileSync(this.playlistFile, 'utf8')
        .split('\n')
        .map((line) => {
          const match = line.match(/^file\s+'(.+)'\s*$/)
          return match ? match[1] : null
        })
        .filter(Boolean)
    } catch {
      return []
    }
  }
}

/*
 * Runs every channel and answers "which channels exist".
 *
 * Each channel costs one encoder process, so this scales with CPU, not
 * with the number of TVs - a thousand TVs on one channel is the same
 * work as one.
 */
class ChannelManager {
  constructor(definitionsFile) {
    this.definitionsFile = definitionsFile
    this.engines = new Map()
  }

  load() {
    let definitions = []

    try {
      definitions = JSON.parse(fs.readFileSync(this.definitionsFile, 'utf8')).channels || []
    } catch (error) {
      console.error('[manager] failed to read channels.json:', error.message)
      return
    }

    for (const definition of definitions) {
      if (!definition.id) {
        continue
      }

      if (this.engines.has(definition.id)) {
        continue
      }

      const engine = new ChannelEngine(definition)

      this.engines.set(definition.id, engine)
    }

    console.log(`[manager] ${this.engines.size} channel(s): ${[...this.engines.keys()].join(', ')}`)
  }

  startAll() {
    for (const engine of this.engines.values()) {
      engine.start()
    }
  }

  stopAll() {
    for (const engine of this.engines.values()) {
      engine.stop()
    }
  }

  get(id) {
    return this.engines.get(id) || null
  }

  has(id) {
    return this.engines.has(id)
  }

  defaultId() {
    return this.engines.keys().next().value || null
  }

  statusAll() {
    return [...this.engines.values()].map((engine) => engine.status())
  }
}

module.exports = { ChannelEngine, ChannelManager, SEGMENT_SECONDS, WINDOW_SEGMENTS }
