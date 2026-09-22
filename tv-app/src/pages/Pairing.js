import Blits from '@lightningjs/blits'

import { getDeviceId, getApiBase, platformName, saveCredentials } from '../utils/device.js'

/*
 * First-boot pairing.
 *
 * Shown exactly once in a TV's life. After an operator claims the code
 * the credentials are stored and this screen is never seen again - not on
 * reboot, not after a power cut, not after the app updates.
 *
 * The alternative, a login screen, means that after a building-wide power
 * cut somebody walks to every TV and types an email address with a remote
 * control. That is the failure mode this design exists to avoid.
 */

export default Blits.Component('Pairing', {
  template: `
    <Element w="1920" h="1080" color="#0e1116">

      <Element x="0" y="0" w="1920" h="8" color="#4ade80" />

      <Text
        x="960"
        y="180"
        content="Connect this TV"
        size="64"
        color="#e6e9ef"
        font="lato"
        mount="{x: 0.5}"
      />

      <Text
        x="960"
        y="278"
        :content="$instruction"
        size="30"
        color="#949cab"
        mount="{x: 0.5}"
      />

      <!-- CODE PANEL -->
      <Element
        x="560"
        y="390"
        w="800"
        h="260"
        color="#171b22"
        :effects="[
          { type: 'radius', props: { radius: 20 } },
          { type: 'border', props: { width: 2, color: '#272d38' } }
        ]"
      />

      <Text
        x="960"
        y="440"
        content="PAIRING CODE"
        size="22"
        color="#6b7280"
        mount="{x: 0.5}"
      />

      <Text
        x="960"
        y="490"
        :content="$code"
        size="110"
        color="#4ade80"
        font="lato"
        mount="{x: 0.5}"
      />

      <Text
        x="960"
        y="720"
        :content="$statusText"
        size="28"
        :color="$statusColor"
        mount="{x: 0.5}"
      />

      <Text
        x="960"
        y="940"
        :content="$deviceLine"
        size="20"
        color="#4b5462"
        mount="{x: 0.5}"
      />

    </Element>
  `,

  state() {
    return {
      code: '------',
      instruction: 'Open the dashboard and enter this code',
      statusText: 'Contacting server...',
      statusColor: '#949cab',
      deviceLine: '',
      pollTimer: null,
      attempt: 0,
    }
  },

  hooks: {
    ready() {
      try {
        console.log('[pairing] ready, device', getDeviceId(), 'api', getApiBase())

        this.deviceLine = `${getDeviceId()}   |   ${getApiBase()}`
      } catch (error) {
        console.error('[pairing] ready failed:', error && error.message)
      }

      this.beginPairing()
    },

    destroy() {
      this.stopPolling()
    },
  },

  methods: {
    /*
     * Retries forever, deliberately.
     *
     * TVs boot faster than servers do, so after a power cut the TV always
     * loses the race to the server coming up. Anything that gives up after
     * N attempts leaves a permanently dark screen that a human has to go
     * and fix.
     */
    async beginPairing() {
      this.attempt += 1

      try {
        console.log('[pairing] POST', `${getApiBase()}/api/device/pair/start`)

        const response = await fetch(`${getApiBase()}/api/device/pair/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            deviceId: getDeviceId(),
            platform: platformName(),
          }),
        })

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const result = await response.json()

        console.log('[pairing] response', JSON.stringify(result))

        if (result.paired) {
          this.onPaired(result)
          return
        }

        this.code = result.code
        this.statusText = 'Waiting for an operator to pair this device'
        this.statusColor = '#949cab'
        this.attempt = 0

        this.startPolling()
      } catch (error) {
        console.error('[pairing] request failed:', error && error.message)

        this.code = '------'
        this.statusText = `Cannot reach server - retrying (${this.attempt})`
        this.statusColor = '#f87171'

        const backoff = Math.min(1000 * this.attempt, 10000)

        setTimeout(() => this.beginPairing(), backoff)
      }
    },

    startPolling() {
      this.stopPolling()

      this.pollTimer = setInterval(() => this.checkStatus(), 2000)
    },

    stopPolling() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },

    async checkStatus() {
      try {
        const response = await fetch(
          `${getApiBase()}/api/device/pair/status?deviceId=${encodeURIComponent(getDeviceId())}`
        )

        if (!response.ok) {
          return
        }

        const result = await response.json()

        if (result.paired) {
          this.onPaired(result)
          return
        }

        // The operator took too long and the code aged out.
        if (result.expiresInSeconds === 0) {
          this.stopPolling()
          this.beginPairing()
        }
      } catch {
        this.statusText = 'Lost connection - still trying'
        this.statusColor = '#fbbf24'
      }
    },

    onPaired(result) {
      this.stopPolling()

      saveCredentials({
        token: result.token,
        channelUrl: result.channelUrl,
        name: result.name,
      })

      this.statusText = 'Paired - starting channel'
      this.statusColor = '#4ade80'

      console.log('[pairing] paired as', result.name, '→', result.channelUrl)

      setTimeout(() => this.$router.to('/play'), 800)
    },
  },
})
