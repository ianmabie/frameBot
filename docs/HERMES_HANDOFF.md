# Hermes handoff

## User's intended outcome

Keep useful default content on the photo frame, swipe among cards, and let the Hermes agent running on the user's machine push new content on demand. The custom Android launcher and push gateway are already operational. The remaining integration is to connect the actual Hermes runtime to the installed client and agree on the default content.

Repository: https://github.com/ianmabie/frameBot

## First action on the existing Mac

Run this using your shell tool:

```sh
/usr/bin/python3 -B "/Users/ian/Library/Application Support/HermesFrame/framectl.py" status
```

The gateway should report `recently_connected: true`, a recent `last_poll`, and the current frame IP. The last observation was `192.168.1.34`, revision 3. IPs can change. If connected, you can immediately send content using this client. No USB, ADB, install, token generation, or router changes are needed for normal pushes.

Recommended tool contract:

```text
frame_text(title, body, id='hermes', focus=true)
  → framectl.py text TITLE BODY --id ID [--no-focus]
frame_image(absolute_file_path, id='image', title='', focus=true)
  → framectl.py image PATH --id ID --title TITLE [--no-focus]
frame_card(payload_json)
  → framectl.py json -  (pass payload through stdin)
frame_status()
  → framectl.py status
frame_remove(id)
  → framectl.py remove ID
```

Use argv arrays and stdin in your tool implementation, rather than shell interpolation of generated content. Pass file paths as separate arguments. Check process exit status, then parse returned JSON. Keep credentials out of tool results and prompts. The CLI reads them privately from the installed gateway directory.

Reuse IDs for recurring updates to prevent filling the 20-card limit. Use `--no-focus` for background refreshes; use focus for an explicit user-requested display. A successful push confirms gateway persistence. Status confirms polling, not that the user has seen the card.

## What has already been completed

- Identified the PF1007L / Allwinner A33 / Android 6.0.1 frame and obtained root wireless ADB through its AiMOR vendor protocol.
- Read boot and recovery twice, matched their SHA-256 hashes, and retained local backups. Did not flash boot/system.
- Built and installed native `com.ian.frame` with offline clock, text/image/HTML cards, swipe navigation, polling, and private offline cache.
- Tested text pushes, swipe, original-app restoration, APK signature, and custom HOME startup after reboot.
- Installed persistent gateway/client under `~/Library/Application Support/HermesFrame/` and a `com.ian.hermes-frame` login service.
- Uploaded the user-supplied photograph, then replaced its `photo` card with a clockwise 90-degree image edit. Last gateway revision 3 was subsequently polled by the frame.
- Removed the temporary router DNS override and stopped the one-shot listener. ADB is closed after reboot; pushes still work.

The photo edit used the built-in image editor. Original and edited photos remain local and are excluded from this repository. For future exact rotation, implement a display rotation option or use a deterministic image transform when the user requests it; preserve originals.

## Existing installation paths

| Path | Contents |
| --- | --- |
| `/Users/ian/Library/Application Support/HermesFrame/` | Live gateway.py, framectl.py, logs, private data |
| `/Users/ian/Library/Application Support/HermesFrame/data/config.json` | Current read/write tokens and gateway configuration; mode 600 |
| `/Users/ian/Library/Application Support/HermesFrame/data/state.json` | Authoritative saved deck |
| `/Users/ian/Library/Application Support/HermesFrame/data/media/` | Uploaded photo bytes |
| `/Users/ian/Library/LaunchAgents/com.ian.hermes-frame.plist` | Persistent per-user login service |
| `/Users/ian/Documents/Codex/2026-10-12/i-need-help-with-a-new/frame-project/` | Original source checkout, ignored key/backups/build/data |
| `.../frame-project/android/build/frame.keystore` | Existing APK signing key; retain it for package updates |
| `.../frame-project/backups/` | Verified boot.img, recovery.img, manifest.json; local only |
| `/private/tmp/frame-wireless/adb35/platform-tools/adb` | Tested ADB 35.0.2; later 37 build crashed on this Mac |
| `/private/tmp/frame-wireless/build-tools/` | Tested JDK/Android tools; temporary |

## Hermes discovery status

No `hermes` executable, `.hermes` directory, Hermes process, Spotlight match, or install in common Mac locations was found. No Hermes tool/skill was configured and no runtime was installed. The similarly named `HermesFrame` folder is this gateway, not the agent. If this handoff is being read by Hermes elsewhere, local push endpoints must be executed on `ian-mini-m6` as the owning user; remote writes to port 8765 are rejected by design. Use an existing authorized remote execution channel to this Mac, or design one with the user.

## Development sequence

1. Read README.md and check live status.
2. Push requested content with the existing client before considering app changes.
3. If developing in a new clone on this Mac, copy the current private config and existing signing key from the original installation into ignored local directories. Do not regenerate tokens/key.
4. Run API/config/protocol tests. Build/verify the APK if Android code changes.
5. Deploy gateway-only changes with deploy_gateway.py; it preserves live data and restarts the LaunchAgent.
6. Android changes require re-enabling wireless ADB: see WIRELESS_ACCESS.md. Keep original AiMOR/OTA installed, and preserve the tested Original photos escape path.
7. Confirm frame behavior using a screenshot or the user when possible. Distinguish accepted/polled from rendered/seen.

The initial repo snapshot includes a portable SDK/JDK build override, fresh-install credential initializer, and repeatable gateway redeploy support. Those source refinements were tested locally; the live gateway has not been redeployed merely to publish the repo. The installed app/gateway continue to serve the working deck.

## Known limitations

- Landscape app layout; image cards fit within the existing header/footer rather than edge-to-edge.
- The photo rotation has been pushed, but no post-reboot screenshot confirms appearance because ADB is closed.
- Source URL can be changed on-device, but the read token is embedded in the APK.
- HTTP bearer authentication on the LAN; no TLS, remote push support, render acknowledgements, or multi-user authorization.
- State response limit 2 MiB and fixed-size typography; avoid giant HTML decks/long titles.
- Old image files and decoded bitmap lifetime need cleanup under sustained use on the ~1 GiB device.
- The actual physical storage is about 15.75 GB despite the listing advertising 32 GB.
- Boot/recovery backups do not cover userdata/system and are not a general restore image.

User has authorized this custom-frame project, wireless debugging, app installation, pushing the provided photo, and creating/uploading this repository. Router credentials were supplied in the original conversation and are not stored in this repo. Obtain them from the user if access is needed later; do not search or publish unrelated credentials.
