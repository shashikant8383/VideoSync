import Blits from '@lightningjs/blits'

import Pairing from './pages/Pairing.js'
import Player from './pages/Player.js'

import { getCredentials } from './utils/device.js'

/*
 * Two screens, and most TVs only ever see one of them.
 *
 * Boot goes straight to the player if this device has been paired before,
 * which after the first setup is every boot forever. No login, no splash,
 * no interaction - power on, picture appears.
 */

export default Blits.Application({
  /*
   * No colour on the application root.
   *
   * The Lightning canvas is layered ABOVE the <video> element so overlays
   * can be drawn over the picture. Painting the root opaque covers the
   * video completely - the text still draws on top, so it looks like the
   * video failed rather than like it is simply hidden.
   *
   * Screens that need a solid background (Pairing) paint their own.
   */
  template: `
    <Element w="1920" h="1080">
      <RouterView />
    </Element>
  `,

  hooks: {
    ready() {
      const { token, channelUrl } = getCredentials()

      if (token && channelUrl) {
        console.log('[app] paired device, going straight to the channel')

        this.$router.to('/play')
        return
      }

      console.log('[app] no credentials, showing pairing')
    },
  },

  routes: [
    { path: '/', component: Pairing },
    { path: '/play', component: Player },
  ],
})
