'use strict'

/*
 * Device registry for the pairing flow.
 *
 * Deliberately debounced and asynchronous. The sync server this POC
 * replaces called fs.writeFileSync on every playback report from every
 * TV, which put a blocking disk write on the event loop N times a second
 * and put a hard ceiling on fleet size. Nothing here is on a hot path -
 * a TV writes once when it pairs and never again - but the habit is
 * worth keeping.
 *
 * For anything real this is Postgres or Redis. A JSON file cannot be
 * shared between two server instances, which means you cannot scale
 * horizontally and cannot deploy without dropping pairing state.
 */

const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const STATE_FILE = path.join(__dirname, 'devices.json')
const WRITE_DEBOUNCE_MS = 500

// Ambiguous glyphs removed - these codes get read off a TV across a room
// and typed by a human. No O/0, no I/1.
const CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
const CODE_LENGTH = 6
const CODE_TTL_MS = 15 * 60 * 1000

class DeviceStore {
  constructor() {
    this.devices = {}
    this.writeTimer = null
    this.load()
  }

  load() {
    if (!fs.existsSync(STATE_FILE)) {
      return
    }

    try {
      const raw = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'))

      this.devices = raw.devices || {}

      console.log(`[store] loaded ${Object.keys(this.devices).length} device(s)`)
    } catch (error) {
      console.error('[store] failed to load state:', error.message)
    }
  }

  save() {
    if (this.writeTimer) {
      return
    }

    this.writeTimer = setTimeout(() => {
      this.writeTimer = null

      const payload = JSON.stringify({ devices: this.devices }, null, 2)

      // Write to a temp file and rename. A crash midway through a direct
      // write leaves a truncated file that fails to parse on next boot,
      // which loses every pairing in the building.
      const temp = `${STATE_FILE}.tmp`

      fs.writeFile(temp, payload, (error) => {
        if (error) {
          console.error('[store] write failed:', error.message)
          return
        }

        fs.rename(temp, STATE_FILE, (renameError) => {
          if (renameError) {
            console.error('[store] rename failed:', renameError.message)
          }
        })
      })
    }, WRITE_DEBOUNCE_MS)
  }

  generateCode() {
    let code = ''

    for (let i = 0; i < CODE_LENGTH; i++) {
      code += CODE_ALPHABET[crypto.randomInt(0, CODE_ALPHABET.length)]
    }

    return code
  }

  /*
   * Called by a TV that has no stored token. Returns a code for a human
   * to type into the dashboard. Repeated calls from the same device
   * reuse the live code so a TV that reboots mid-setup doesn't change
   * the number on screen while someone is typing it.
   */
  startPairing(deviceId, info = {}) {
    const existing = this.devices[deviceId]

    if (existing && existing.paired) {
      return { alreadyPaired: true, device: existing }
    }

    if (existing && existing.code && Date.now() < existing.codeExpiresAt) {
      return { alreadyPaired: false, device: existing }
    }

    const device = {
      deviceId,
      code: this.generateCode(),
      codeExpiresAt: Date.now() + CODE_TTL_MS,
      paired: false,
      token: null,
      channelId: null,
      name: info.name || null,
      platform: info.platform || 'unknown',
      createdAt: existing ? existing.createdAt : Date.now(),
      lastSeenAt: Date.now(),
    }

    this.devices[deviceId] = device

    this.save()

    console.log(`[store] pairing started for ${deviceId} - code ${device.code}`)

    return { alreadyPaired: false, device }
  }

  findByCode(code) {
    const normalized = String(code || '').trim().toUpperCase()

    return (
      Object.values(this.devices).find(
        (device) =>
          device.code === normalized &&
          !device.paired &&
          Date.now() < device.codeExpiresAt
      ) || null
    )
  }

  /*
   * Called from the dashboard by an operator. This is the trust boundary:
   * a device becomes authorised here and nowhere else.
   */
  claim(code, channelId, name) {
    const device = this.findByCode(code)

    if (!device) {
      return null
    }

    device.paired = true
    device.token = crypto.randomBytes(24).toString('hex')
    device.channelId = channelId || 'main'
    device.name = name || device.name || `TV ${Object.keys(this.devices).length}`
    device.pairedAt = Date.now()
    device.code = null
    device.codeExpiresAt = 0

    this.save()

    console.log(`[store] device ${device.deviceId} claimed as "${device.name}"`)

    return device
  }

  getByDeviceId(deviceId) {
    return this.devices[deviceId] || null
  }

  /*
   * Move a TV to a different channel.
   *
   * The TV is not told directly - nothing pushes to a TV. It discovers
   * the change on its next config heartbeat (within 30s) and reattaches
   * to the new manifest by itself.
   */
  setChannel(deviceId, channelId) {
    const device = this.devices[deviceId]

    if (!device) {
      return null
    }

    device.channelId = channelId

    this.save()

    console.log(`[store] device ${deviceId} moved to channel "${channelId}"`)

    return device
  }

  getByToken(token) {
    if (!token) {
      return null
    }

    return Object.values(this.devices).find((device) => device.token === token) || null
  }

  touch(device) {
    device.lastSeenAt = Date.now()
    this.save()
  }

  unpair(deviceId) {
    const device = this.devices[deviceId]

    if (!device) {
      return false
    }

    delete this.devices[deviceId]

    this.save()

    console.log(`[store] device ${deviceId} removed`)

    return true
  }

  list() {
    return Object.values(this.devices)
      .sort((a, b) => (b.lastSeenAt || 0) - (a.lastSeenAt || 0))
      .map((device) => ({
        deviceId: device.deviceId,
        name: device.name,
        platform: device.platform,
        paired: device.paired,
        code: device.code,
        channelId: device.channelId,
        lastSeenAt: device.lastSeenAt,
        // A TV polls config every 30s, so anything quiet for 90s is gone.
        online: Date.now() - (device.lastSeenAt || 0) < 90000,
      }))
  }
}

module.exports = { DeviceStore }
