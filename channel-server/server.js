'use strict'

/*
 * Channel origin + device API.
 *
 * Three jobs, deliberately kept separate:
 *
 *   /channels/<id>/* a live HLS stream. Anonymous HTTP GETs. No session,
 *                    no handshake - a TV "connects" by fetching a manifest
 *                    and that is the entire protocol. This is what makes
 *                    the stream CDN-cacheable and lets one origin serve a
 *                    fleet of any size.
 *
 *   /api/device/*    pairing and config. A TV uses this exactly twice in
 *                    its life: once to pair, then once per boot to learn
 *                    which channel it is on. Never during playback.
 *
 *   /api/admin/*     the operator dashboard. The only place a device can
 *                    be authorised.
 *
 * Zero dependencies, so the server runs straight from a clone with no
 * npm install.
 */

const http = require('http')
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const os = require('os')

const { ChannelManager } = require('./engine')
const { DeviceStore } = require('./store')

const PORT = Number(process.env.PORT) || 4000
const PUBLIC_DIR = path.join(__dirname, 'public')
const CHANNELS_FILE = path.join(__dirname, 'channels.json')

const store = new DeviceStore()
const channels = new ChannelManager(CHANNELS_FILE)

channels.load()

// ---------------------------------------------------------------------------
// HELPERS
// ---------------------------------------------------------------------------

function sendJson(res, status, body) {
  const payload = JSON.stringify(body)

  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
    'Cache-Control': 'no-store',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  })

  res.end(payload)
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = ''
    let size = 0

    req.on('data', (chunk) => {
      size += chunk.length

      // Any device payload here is a few hundred bytes. Anything larger is
      // either a bug or someone probing.
      if (size > 64 * 1024) {
        reject(new Error('Body too large'))
        req.destroy()
        return
      }

      body += chunk
    })

    req.on('end', () => {
      if (!body) {
        resolve({})
        return
      }

      try {
        resolve(JSON.parse(body))
      } catch {
        reject(new Error('Invalid JSON'))
      }
    })

    req.on('error', reject)
  })
}

function bearerToken(req) {
  const header = req.headers.authorization || ''

  return header.startsWith('Bearer ') ? header.slice(7) : null
}

function localAddress() {
  for (const entries of Object.values(os.networkInterfaces())) {
    for (const entry of entries || []) {
      if (entry.family === 'IPv4' && !entry.internal) {
        return entry.address
      }
    }
  }

  return '127.0.0.1'
}

/*
 * The URL a TV should pull. Derived from the Host header the TV actually
 * reached us on, rather than hardcoded - an Android emulator arrives via
 * 10.0.2.2, a real TV via the LAN address, and both need to be told the
 * name that works from where they are standing. Hardcoding this is what
 * left the previous POC with a 192.168.x.x literal in its source.
 */
function channelUrlFor(req, channelId) {
  const host = req.headers.host || `${localAddress()}:${PORT}`

  const id = channels.has(channelId) ? channelId : channels.defaultId()

  return `http://${host}/channels/${id}/live.m3u8`
}

// A device with no assignment, or one pointing at a channel that no
// longer exists, falls back to the first channel rather than going dark.
function resolveChannelId(device) {
  return device && channels.has(device.channelId) ? device.channelId : channels.defaultId()
}

// ---------------------------------------------------------------------------
// STATIC / HLS
// ---------------------------------------------------------------------------

const MIME = {
  '.m3u8': 'application/vnd.apple.mpegurl',
  '.ts': 'video/mp2t',
  '.m4s': 'video/iso.segment',
  '.mp4': 'video/mp4',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
}

function serveStatic(req, res, urlPath) {
  const relative = urlPath.replace(/^\/+/, '')

  const filePath = path.join(PUBLIC_DIR, relative)

  // Refuse anything that escapes the public directory.
  if (!filePath.startsWith(PUBLIC_DIR)) {
    sendJson(res, 403, { error: 'Forbidden' })
    return
  }

  fs.stat(filePath, (error, stat) => {
    if (error || !stat.isFile()) {
      sendJson(res, 404, { error: 'Not found' })
      return
    }

    const ext = path.extname(filePath).toLowerCase()

    /*
     * Cache policy is the part that breaks live streaming when it is
     * wrong, and it breaks it for everyone at once.
     *
     * The manifest is rewritten every few seconds and MUST NOT be cached;
     * a CDN holding it for 60s stalls every TV simultaneously and looks
     * exactly like an encoder failure while you debug it.
     *
     * Segments never change once written, so they cache forever.
     */
    const headers = {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Content-Length': stat.size,
      'Access-Control-Allow-Origin': '*',
    }

    if (ext === '.m3u8') {
      headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    } else if (ext === '.ts' || ext === '.m4s') {
      headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    } else {
      headers['Cache-Control'] = 'no-cache'
    }

    res.writeHead(200, headers)

    fs.createReadStream(filePath).pipe(res)
  })
}

// ---------------------------------------------------------------------------
// ROUTES
// ---------------------------------------------------------------------------

async function handleApi(req, res, url) {
  const route = `${req.method} ${url.pathname}`

  // -- device: begin pairing -------------------------------------------------
  if (route === 'POST /api/device/pair/start') {
    const body = await readBody(req)

    const deviceId = String(body.deviceId || '').trim()

    if (!deviceId || deviceId.length > 128) {
      sendJson(res, 400, { error: 'deviceId is required' })
      return
    }

    const { alreadyPaired, device } = store.startPairing(deviceId, {
      platform: body.platform,
      name: body.name,
    })

    if (alreadyPaired) {
      sendJson(res, 200, {
        paired: true,
        token: device.token,
        channelUrl: channelUrlFor(req, resolveChannelId(device)),
        name: device.name,
      })
      return
    }

    sendJson(res, 200, {
      paired: false,
      code: device.code,
      expiresInSeconds: Math.max(0, Math.round((device.codeExpiresAt - Date.now()) / 1000)),
    })
    return
  }

  // -- device: poll until an operator claims it ------------------------------
  if (route === 'GET /api/device/pair/status') {
    const deviceId = url.searchParams.get('deviceId')

    const device = store.getByDeviceId(deviceId)

    if (!device) {
      sendJson(res, 404, { error: 'Unknown device' })
      return
    }

    if (!device.paired) {
      sendJson(res, 200, {
        paired: false,
        code: device.code,
        expiresInSeconds: Math.max(0, Math.round((device.codeExpiresAt - Date.now()) / 1000)),
      })
      return
    }

    store.touch(device)

    sendJson(res, 200, {
      paired: true,
      token: device.token,
      channelUrl: channelUrlFor(req, resolveChannelId(device)),
      name: device.name,
    })
    return
  }

  /*
   * -- device: per-boot config ----------------------------------------------
   *
   * The only authenticated device endpoint, and it is not on the playback
   * path - a TV calls this at boot and then periodically as a heartbeat.
   * If it fails, playback carries on regardless. Nothing about the video
   * depends on this server staying up once a TV knows its channel URL.
   */
  if (route === 'GET /api/device/config') {
    const device = store.getByToken(bearerToken(req))

    if (!device) {
      sendJson(res, 401, { error: 'Unauthorized' })
      return
    }

    store.touch(device)

    const channelId = resolveChannelId(device)

    sendJson(res, 200, {
      channelUrl: channelUrlFor(req, channelId),
      channelId,
      name: device.name,
      channel: channels.get(channelId) ? channels.get(channelId).status() : null,
    })
    return
  }

  // -- admin -----------------------------------------------------------------
  if (route === 'GET /api/admin/devices') {
    sendJson(res, 200, { devices: store.list(), defaultChannel: channels.defaultId() })
    return
  }

  if (route === 'GET /api/admin/channels') {
    sendJson(res, 200, { channels: channels.statusAll() })
    return
  }

  /*
   * Move a TV to another channel. The TV is never pushed to - it notices
   * on its next heartbeat and reattaches itself.
   */
  if (route === 'POST /api/admin/device/channel') {
    const body = await readBody(req)

    if (!channels.has(body.channelId)) {
      sendJson(res, 400, { error: 'Unknown channel' })
      return
    }

    const device = store.setChannel(body.deviceId, body.channelId)

    if (!device) {
      sendJson(res, 404, { error: 'Unknown device' })
      return
    }

    sendJson(res, 200, { success: true, channelId: device.channelId })
    return
  }

  if (route === 'POST /api/admin/claim') {
    const body = await readBody(req)

    const channelId = channels.has(body.channelId) ? body.channelId : channels.defaultId()

    const device = store.claim(body.code, channelId, body.name)

    if (!device) {
      sendJson(res, 404, { error: 'No device is waiting with that code' })
      return
    }

    sendJson(res, 200, {
      success: true,
      device: { deviceId: device.deviceId, name: device.name, channelId: device.channelId },
    })
    return
  }

  if (route === 'POST /api/admin/unpair') {
    const body = await readBody(req)

    sendJson(res, 200, { success: store.unpair(body.deviceId) })
    return
  }

  if (route === 'POST /api/admin/reload') {
    const body = await readBody(req)

    const engine = channels.get(body.channelId)

    if (!engine) {
      sendJson(res, 400, { error: 'Unknown channel' })
      return
    }

    engine.reload('operator requested')

    sendJson(res, 200, { success: true })
    return
  }

  if (route === 'GET /api/status') {
    sendJson(res, 200, {
      channels: channels.statusAll(),
      devices: store.list().length,
      serverTime: Date.now(),
    })
    return
  }

  sendJson(res, 404, { error: 'Not found' })
}

// ---------------------------------------------------------------------------
// SERVER
// ---------------------------------------------------------------------------

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`)

  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    })
    res.end()
    return
  }

  if (url.pathname.startsWith('/api/')) {
    handleApi(req, res, url).catch((error) => {
      console.error('[api] error:', error.message)
      sendJson(res, 400, { error: error.message })
    })
    return
  }

  if (url.pathname === '/' || url.pathname === '/admin') {
    serveStatic(req, res, '/admin.html')
    return
  }

  serveStatic(req, res, url.pathname)
})

server.listen(PORT, '0.0.0.0', () => {
  const address = localAddress()

  console.log('')
  console.log('  CHANNEL SERVER')
  console.log('  ─────────────────────────────────────────────')
  console.log(`  dashboard   http://${address}:${PORT}/`)

  for (const status of channels.statusAll()) {
    console.log(`  ${status.id.padEnd(11)} http://${address}:${PORT}/channels/${status.id}/live.m3u8`)
  }

  console.log(`  emulator    http://10.0.2.2:${PORT}/channels/<id>/live.m3u8`)
  console.log('  ─────────────────────────────────────────────')
  console.log('')

  channels.startAll()
})

function shutdown() {
  console.log('\n[server] shutting down')

  channels.stopAll()

  server.close(() => process.exit(0))

  // Don't hang forever on a stuck connection.
  setTimeout(() => process.exit(0), 3000).unref()
}

process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
