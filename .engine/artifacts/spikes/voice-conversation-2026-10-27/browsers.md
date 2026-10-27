# Phones: what a hands-free voice web page can do (desk research, 2026-10-27)

Done by a research subagent with web search; nothing here was tried on a real phone (the server has no iPhone or
Android device). Confidence: H = vendor doc / compat data, M = consistent bug reports, L = thin evidence.

| # | iPhone Safari | Android Chrome |
|---|---|---|
| 1. Mic open 30 min, foreground, screen on | No documented limit; tracks can end after background / call / another tab — watch `track.onended`, reopen. M [1][2] | No documented limit. M |
| 2. Play later without a new tap | AudioContext resumed in the tap usually stays `running`; a call, Siri, lock or BT re-pair → `interrupted`, `resume()` without a tap may fail. Home-screen app on iOS 26: `resume()` reported hanging. M [3][4][5][6] | Sticky user activation: the context keeps playing. H |
| 3. Earpiece / quiet playback while mic on | Known: WebKit bug 326286 (open, iOS 26.2–27): `echoCancellation:true` → loudspeaker but crackles; false → earpiece, quiet. `navigator.audioSession.type` (Safari 16.4+): auto, playback, transient, transient-solo, ambient, play-and-record; none forces the loudspeaker. M–H [7][8][9][10][11] | API absent; earpiece problem not reported. H / L |
| 4. Bluetooth car (HFP) | play-and-record moves BT from A2DP to HFP: car mic and speakers at call quality. L–M [12] | Chromium (Nov 2024) sets communication mode with a BT mic → SCO output. Whether the default mic is the car's — not confirmed. M / L [13] |
| 5. Screen off / locked / background | Tab: a 2023 report says the mic keeps working locked; home-screen apps lose it; older reports: tracks end after 30–60 s. Wake Lock: tab since 16.4, home-screen app since 18.4. M / H [2][14][15][16] | Reports: capture and playback stop soon after the screen goes off. Wake Lock since Chrome 84. L / H [17][18][19][15] |
| 6. Codecs | MediaRecorder `audio/mp4` since 14.1, webm/opus since 18.4. Opus playback in `<audio>` from 18.4; decodeAudioData of Ogg/Opus not confirmed. MP3 safe. M [20][21][22][23] | Records webm/opus; plays Ogg/Opus and MP3. H [21] |
| 7. echoCancellation vs the page's own playback | Cancels all browser audio, but crackles on iOS 26.2–27 (bug 326286). M [10][24] | Desktop Chrome used only WebRTC remote audio as reference (crbug 687574); Android — platform AEC, unverified. L [24] |

Consequences taken into the design: half-duplex (the page does not listen while it speaks — no reliance on echo
cancellation); MP3 replies (play everywhere); Screen Wake Lock while the mode is on, re-requested when the page is
visible again; the mic stream kept open for the whole mode and reopened if its track ends; the AudioContext created
in the one tap and resumed when it is `interrupted`/`suspended`; when it cannot be resumed — a visible «tap to go on».

Sources: [1] https://bugs.webkit.org/show_bug.cgi?id=204681 [2] https://bugs.webkit.org/show_bug.cgi?id=179964
[3] https://webkit.org/blog/7763/a-closer-look-into-webrtc/ [4] https://github.com/microsoft/TypeScript/issues/61823
[5] https://bugs.webkit.org/show_bug.cgi?id=263627 [6] https://bugs.webkit.org/show_bug.cgi?id=291892
[7] https://bugs.webkit.org/show_bug.cgi?id=326286 [8] https://bugs.webkit.org/show_bug.cgi?id=218012
[9] https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/Navigator.json
[10] https://developer.mozilla.org/en-US/docs/Web/API/AudioSession/type [11] https://www.w3.org/TR/audio-session/
[12] https://www.val.town/embed/x/c15r/mochi/design/ios-bluetooth-audio.md
[13] https://chromium.googlesource.com/chromium/src/+/78d0de138346e6edfc8c33bdd22c45b3eec4f3d0
[14] https://bugs.webkit.org/show_bug.cgi?id=254545 [15] MDN BCD wakeLock (same JSON as [9])
[16] https://bugs.webkit.org/show_bug.cgi?id=255363 [17] https://lists.w3.org/Archives/Public/public-webrtc-logs/2020Mar/0129.html
[18] https://phonon.atlassian.net/wiki/x/fwH8HQ [19] https://groups.google.com/a/chromium.org/d/msg/blink-dev/XRqy8mIOWps/Btb4o__1AQAJ
[20] https://addpipe.com/media-recorder-api-demo/ [21] https://raw.githubusercontent.com/Fyrd/caniuse/main/features-json/opus.json
[22] https://frequal.com/java/OggOpusStillNotWorkingInSafari18_4.html [23] https://bugs.webkit.org/show_bug.cgi?id=327697
[24] https://lists.w3.org/Archives/Public/public-webrtc-logs/2019May/0147.html
