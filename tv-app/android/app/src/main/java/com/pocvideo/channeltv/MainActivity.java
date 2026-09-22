package com.pocvideo.channeltv;

import android.os.Bundle;
import android.view.WindowManager;
import android.webkit.WebSettings;

import com.getcapacitor.BridgeActivity;

/*
 * Signage-oriented WebView setup.
 *
 * A TV running a channel is unattended: nobody is there to dismiss a
 * screensaver, tap to start playback, or wake the display. Each setting
 * below removes one assumption the platform makes about there being a
 * person in front of the screen.
 */
public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        /*
         * Without this the display sleeps and the channel is still
         * "playing" to a black screen.
         */
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        WebSettings settings = this.bridge.getWebView().getSettings();

        /*
         * The default requires a user gesture before media may play. On a
         * TV there is no gesture, so autoplay silently never starts. This
         * is also what allows playback with audio rather than forcing the
         * muted workaround.
         */
        settings.setMediaPlaybackRequiresUserGesture(false);

        settings.setDomStorageEnabled(true);

        /*
         * The app is served from the WebView's own origin while the
         * channel and API are plain HTTP on the LAN.
         */
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
    }
}
