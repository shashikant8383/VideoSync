import Blits from '@lightningjs/blits'
import Hls from 'hls.js'

import {
  getCredentials,
  clearCredentials,
  getApiBase,
  syncServerClock,
  serverNow,
  clockInfo,
} from '../utils/device.js'

/*
 * The channel player.
 *
 * This is the whole client. It opens a live HLS manifest and plays it,
 * the way a television tunes a broadcast. There is no playlist logic, no
 * schedule, no position arithmetic, no coordination with other TVs, and
 * no state reported back to a server. What is on air is decided upstream
 * by the channel engine; this end just displays it.
 *
 * Two behaviours are worth reading closely:
 *
 *   retry forever    a TV that gives up is a TV somebody has to visit.
 *
 *   latency hold     tuning the same manifest puts every TV on the same
 *                    *channel*, not the same *frame*. Players each pick
 *                    their own start point near the live edge and, once
 *                    apart, nothing pulls them back together. Holding a
 *                    fixed latency behind a shared clock is what turns
 *                    "same channel" into "same frame".
 */

// How far behind the live edge to sit. Every TV targets this same number,
// which is what makes them agree. Too small and a slow segment fetch
// underruns the buffer; too large and the segment ages out of the window.
const TARGET_LATENCY_MS = 12000

// Below this, leave playback alone. Chasing smaller errors than this just
// makes the picture judder for no visible benefit.
const DEADBAND_MS = 300

// Between the deadband and this, correct with playback rate. Beyond it,
// seek - rate correction would take too long to close the gap.
const SEEK_THRESHOLD_MS = 5000

// +/-2%. The previous POC used +/-5%, which is audible as a pitch shift
// on anything with sound.
const RATE_FAST = 1.02
const RATE_SLOW = 0.98

export default Blits.Component('Player', {
  template: `
    <!--
      No colour on the root: it must stay transparent so the video
      underneath shows through. Only the overlay strip is painted.
    -->
    <Element w="1920" h="1080">

      <Element
        x="0"
        y="0"
        w="1160"
        h="118"
        color="#000000"
        :alpha="$overlayAlpha"
        :effects="[
          { type: 'radius', props: { radius: 0 } }
        ]"
      />

      <Text
        x="40"
        y="26"
        :content="$statusLine"
        size="30"
        color="#e6e9ef"
        :alpha="$overlayAlpha"
      />

      <Text
        x="40"
        y="70"
        :content="$syncLine"
        size="26"
        :color="$syncColor"
        :alpha="$overlayAlpha"
      />

    </Element>
  `,

  state() {
    return {
      statusLine: 'Starting channel...',
      syncLine: '',
      syncColor: '#949cab',
      overlayAlpha: 1,

      video: null,
      hls: null,

      channelUrl: null,

      tickTimer: null,
      heartbeatTimer: null,

      retryDelay: 1000,
      retryCount: 0,

      buffering: false,
      lastDriftMs: 0,
    }
  },

  hooks: {
    async ready() {
      const { channelUrl } = getCredentials()

      if (!channelUrl) {
        this.$router.to('/')
        return
      }

      this.channelUrl = channelUrl

      console.log('[player] channel:', channelUrl)

      this.createVideo()

      // Refines drift correction. Playback does not wait on it.
      syncServerClock().then(() => {
        console.log('[player] clock ready:', clockInfo())
      })

      this.attach()

      this.startTick()
      this.startHeartbeat()

      this.$focus()
    },

    destroy() {
      this.stopTick()
      this.stopHeartbeat()
      this.teardown()
    },
  },

  input: {
    // Hide the diagnostic overlay. A shipped channel shows only video.
    space() {
      this.overlayAlpha = this.overlayAlpha ? 0 : 1
    },

    back() {
      this.overlayAlpha = this.overlayAlpha ? 0 : 1
    },
  },

  methods: {
    createVideo() {
      const video = document.createElement('video')

      video.id = 'channel-video'

      video.style.position = 'fixed'
      video.style.left = '0'
      video.style.top = '0'
      video.style.width = '100vw'
      video.style.height = '100vh'
      video.style.objectFit = 'contain'
      video.style.backgroundColor = '#000000'
      video.style.zIndex = '1'

      video.autoplay = true
      video.playsInline = true
      video.controls = false

      /*
       * Muted because a TV has no user gesture to unlock audio with, and
       * browsers block unmuted autoplay without one. To ship with sound,
       * set mediaPlaybackRequiresUserGesture to false in the Capacitor
       * Android config and drop this line.
       */
      video.muted = true

      document.body.appendChild(video)

      video.addEventListener('waiting', () => {
        this.buffering = true
      })

      video.addEventListener('playing', () => {
        this.buffering = false
        this.retryDelay = 1000
      })

      this.video = video
    },

    attach() {
      if (!this.video) {
        return
      }

      this.teardownHls()

      this.statusLine = 'Loading channel...'

      if (Hls.isSupported()) {
        const hls = new Hls({
          lowLatencyMode: false,

          // Where hls.js aims on its own. Setting it to the same value the
          // drift loop targets means the correction starts near zero
          // instead of fighting the player's own default.
          liveSyncDuration: TARGET_LATENCY_MS / 1000,
          liveMaxLatencyDuration: TARGET_LATENCY_MS / 1000 + 18,

          backBufferLength: 30,
          maxBufferLength: 30,
        })

        this.hls = hls

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          console.log('[player] manifest parsed')

          this.statusLine = 'On air'
          this.retryDelay = 1000
          this.retryCount = 0

          this.play()
        })

        hls.on(Hls.Events.ERROR, (event, data) => {
          if (!data || !data.fatal) {
            return
          }

          console.error('[player] fatal hls error:', data.type, data.details)

          if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
            this.statusLine = 'Media error - recovering'

            try {
              hls.recoverMediaError()
              return
            } catch {
              // Fall through to a full reattach.
            }
          }

          this.scheduleReattach(data.details || data.type)
        })

        hls.loadSource(this.channelUrl)
        hls.attachMedia(this.video)

        return
      }

      // Native HLS (Safari, some TV browsers).
      if (this.video.canPlayType('application/vnd.apple.mpegurl')) {
        this.video.src = this.channelUrl

        this.video.addEventListener('error', () => this.scheduleReattach('native error'))

        this.statusLine = 'On air'

        this.play()
        return
      }

      this.statusLine = 'HLS not supported on this device'
    },

    play() {
      if (!this.video) {
        return
      }

      this.video.play().catch((error) => {
        console.error('[player] play rejected:', error.message)

        // Autoplay was blocked despite muted. Retry on the next tick
        // rather than giving up - some WebViews allow it a moment later.
        setTimeout(() => this.play(), 1000)
      })
    },

    /*
     * Never stops trying. The channel may be down, the network may be
     * out, the server may not have booted yet. All of those resolve on
     * their own and the TV should come back without anyone touching it.
     */
    scheduleReattach(reason) {
      this.retryCount += 1

      const delay = this.retryDelay

      this.statusLine = `Reconnecting - ${reason} (${this.retryCount})`

      console.log(`[player] reattaching in ${delay}ms after ${reason}`)

      this.retryDelay = Math.min(this.retryDelay * 2, 15000)

      setTimeout(() => this.attach(), delay)
    },

    // ------------------------------------------------------------------
    // LATENCY HOLD
    // ------------------------------------------------------------------

    /*
     * Where this TV should be, expressed as a wall-clock instant.
     *
     * EXT-X-PROGRAM-DATE-TIME gives every segment a real timestamp, so
     * hls.playingDate is the wall-clock time of the frame on screen right
     * now. Comparing that against a shared target is what lets two TVs
     * that never talk to each other land on the same frame.
     */
    driftMs() {
      if (!this.hls || !this.hls.playingDate) {
        return null
      }

      const targetInstant = serverNow() - TARGET_LATENCY_MS

      return this.hls.playingDate.getTime() - targetInstant
    },

    correctDrift() {
      if (!this.video || this.buffering || this.video.paused) {
        return
      }

      const drift = this.driftMs()

      if (drift === null) {
        return
      }

      this.lastDriftMs = drift

      const absDrift = Math.abs(drift)

      if (absDrift <= DEADBAND_MS) {
        if (this.video.playbackRate !== 1) {
          this.video.playbackRate = 1
        }
        return
      }

      if (absDrift <= SEEK_THRESHOLD_MS) {
        // Ahead of target -> ease off. Behind -> catch up.
        this.video.playbackRate = drift > 0 ? RATE_SLOW : RATE_FAST
        return
      }

      // Too far out to rate-correct. Seek, but only within what is
      // actually buffered - seeking outside the seekable range on a live
      // stream drops the player off the back of the window.
      this.video.playbackRate = 1

      const seekable = this.video.seekable

      if (!seekable || seekable.length === 0) {
        return
      }

      const target = this.video.currentTime - drift / 1000

      const clamped = Math.min(
        Math.max(target, seekable.start(0) + 1),
        seekable.end(seekable.length - 1) - 1
      )

      if (Number.isFinite(clamped)) {
        console.log(`[player] drift ${Math.round(drift)}ms - seeking`)

        this.video.currentTime = clamped
      }
    },

    startTick() {
      this.stopTick()

      this.tickTimer = setInterval(() => {
        this.correctDrift()
        this.updateOverlay()
      }, 1000)
    },

    stopTick() {
      if (this.tickTimer) {
        clearInterval(this.tickTimer)
        this.tickTimer = null
      }
    },

    /*
     * Heartbeat, not a sync mechanism. It tells the dashboard this screen
     * is alive and picks up a channel reassignment. Playback continues
     * perfectly well when it fails.
     */
    startHeartbeat() {
      this.stopHeartbeat()

      const beat = async () => {
        const { token } = getCredentials()

        if (!token) {
          return
        }

        try {
          const response = await fetch(`${getApiBase()}/api/device/config`, {
            headers: { Authorization: `Bearer ${token}` },
          })

          if (response.status === 401) {
            /*
             * Removed from the dashboard. The server never pushes, so
             * this 401 is how the TV finds out.
             *
             * The stored token must be discarded, not just navigated
             * away from: App.js sends a device with credentials straight
             * to the player on boot, so keeping them would bounce the TV
             * between player and pairing on every restart.
             */
            console.log('[player] device was unpaired - clearing credentials')

            clearCredentials()

            this.$router.to('/')
            return
          }

          const config = await response.json()

          if (config.channelUrl && config.channelUrl !== this.channelUrl) {
            console.log('[player] channel changed:', config.channelUrl)

            this.channelUrl = config.channelUrl

            this.attach()
          }
        } catch {
          // Offline. Keep playing.
        }
      }

      beat()

      this.heartbeatTimer = setInterval(beat, 30000)
    },

    stopHeartbeat() {
      if (this.heartbeatTimer) {
        clearInterval(this.heartbeatTimer)
        this.heartbeatTimer = null
      }
    },

    updateOverlay() {
      if (!this.video) {
        return
      }

      const drift = this.lastDriftMs

      const channelTime = this.hls && this.hls.playingDate
        ? this.hls.playingDate.toISOString().slice(11, 19)
        : '--:--:--'

      let state = 'ON AIR'

      if (this.buffering) {
        state = 'BUFFERING'
      } else if (this.video.paused) {
        state = 'PAUSED'
      }

      this.statusLine = `${state}   |   channel time ${channelTime}`

      const absDrift = Math.abs(drift)

      this.syncColor = absDrift <= DEADBAND_MS ? '#4ade80' : absDrift <= SEEK_THRESHOLD_MS ? '#fbbf24' : '#f87171'

      this.syncLine =
        `drift ${drift >= 0 ? '+' : ''}${Math.round(drift)}ms` +
        `   |   rate ${this.video.playbackRate.toFixed(2)}x` +
        `   |   clock ${clockInfo().offset >= 0 ? '+' : ''}${clockInfo().offset}ms` +
        `   |   ${this.video.videoWidth}x${this.video.videoHeight}` +
        `   |   t ${this.video.currentTime.toFixed(1)}s`
    },

    teardownHls() {
      if (this.hls) {
        try {
          this.hls.destroy()
        } catch (error) {
          console.error('[player] hls destroy failed:', error.message)
        }

        this.hls = null
      }
    },

    teardown() {
      this.teardownHls()

      if (this.video) {
        try {
          this.video.pause()
          this.video.removeAttribute('src')
          this.video.load()

          if (this.video.parentNode) {
            this.video.parentNode.removeChild(this.video)
          }
        } catch (error) {
          console.error('[player] video teardown failed:', error.message)
        }

        this.video = null
      }
    },
  },
})
