/*
 * Device identity, persisted credentials, and the server clock.
 *
 * A TV is an appliance, not a personal device. It identifies itself with
 * a generated id it keeps forever, and is authorised once by an operator.
 * There is no user, no email, no password, and nothing for anyone to type
 * with a remote control after the first setup.
 */

const STORAGE_KEYS = {
  deviceId: 'tv.deviceId',
  token: 'tv.token',
  channelUrl: 'tv.channelUrl',
  name: 'tv.name',
}

/*
 * localStorage throws in some WebView configurations rather than simply
 * returning null, and a TV that crashes on boot because storage is
 * unavailable is worse than a TV that re-pairs.
 */
function read(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, value)
    return true
  } catch {
    return false
  }
}

function remove(key) {
  try {
    localStorage.removeItem(key)
  } catch {
    // Nothing useful to do.
  }
}

export function getDeviceId() {
  let id = read(STORAGE_KEYS.deviceId)

  if (id) {
    return id
  }

  id = 'tv_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4)

  write(STORAGE_KEYS.deviceId, id)

  return id
}

export function getCredentials() {
  return {
    token: read(STORAGE_KEYS.token),
    channelUrl: read(STORAGE_KEYS.channelUrl),
    name: read(STORAGE_KEYS.name),
  }
}

export function saveCredentials({ token, channelUrl, name }) {
  if (token) write(STORAGE_KEYS.token, token)
  if (channelUrl) write(STORAGE_KEYS.channelUrl, channelUrl)
  if (name) write(STORAGE_KEYS.name, name)
}

export function clearCredentials() {
  remove(STORAGE_KEYS.token)
  remove(STORAGE_KEYS.channelUrl)
  remove(STORAGE_KEYS.name)
}

/*
 * Where the control API lives.
 *
 * An Android emulator reaches the host machine at 10.0.2.2; a browser on
 * the dev machine reaches it at its own hostname. Deriving this instead
 * of hardcoding it is why there is no 192.168.x.x literal anywhere in
 * this codebase.
 *
 * VITE_API_BASE overrides for a real deployment.
 */
export function getApiBase() {
  const configured = import.meta.env.VITE_API_BASE

  if (configured) {
    return configured.replace(/\/+$/, '')
  }

  const isAndroidWebView = /Android/i.test(navigator.userAgent)

  if (isAndroidWebView) {
    return 'http://10.0.2.2:4000'
  }

  const host = (typeof window !== 'undefined' && window.location && window.location.hostname) || 'localhost'

  return `http://${host}:4000`
}

export function platformName() {
  if (/Android/i.test(navigator.userAgent)) return 'android-tv'
  if (/Tizen/i.test(navigator.userAgent)) return 'tizen'
  if (/Web0S|webOS/i.test(navigator.userAgent)) return 'webos'
  return 'browser'
}

// ---------------------------------------------------------------------------
// SERVER CLOCK
// ---------------------------------------------------------------------------

let clockOffset = 0
let clockMeasured = false

/*
 * Round-trip-corrected clock offset.
 *
 * The naive version of this - offset = serverTime - Date.now() measured
 * after the response lands - bakes in half the round trip, so every TV is
 * biased by its own latency and two TVs on different links disagree by
 * the difference. Recording t0 before the request and taking the midpoint
 * removes that. Several samples are taken and the one with the lowest
 * round trip wins, because the fastest exchange is the least distorted.
 *
 * This only refines sync; playback works without it.
 */
export async function syncServerClock(samples = 4) {
  let best = null

  for (let i = 0; i < samples; i++) {
    const t0 = Date.now()

    try {
      const response = await fetch(`${getApiBase()}/api/status`, { cache: 'no-store' })

      const t3 = Date.now()

      if (!response.ok) continue

      const body = await response.json()

      const serverTime = Number(body.serverTime)

      if (!Number.isFinite(serverTime)) continue

      const roundTrip = t3 - t0

      const offset = serverTime - (t0 + roundTrip / 2)

      if (!best || roundTrip < best.roundTrip) {
        best = { offset, roundTrip }
      }
    } catch {
      // Offline. The previous offset, or zero, stays in effect.
    }
  }

  if (best) {
    clockOffset = best.offset
    clockMeasured = true

    console.log(`[clock] offset ${Math.round(best.offset)}ms (rtt ${best.roundTrip}ms)`)
  }

  return { offset: clockOffset, measured: clockMeasured }
}

export function serverNow() {
  return Date.now() + clockOffset
}

export function clockInfo() {
  return { offset: Math.round(clockOffset), measured: clockMeasured }
}
