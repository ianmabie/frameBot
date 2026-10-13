# Hermes Frame

A working custom launcher for a humblestead PF1007L photo frame, plus a persistent Mac gateway that lets Hermes push content. The frame has a default clock and agent card; swipe between those and added text, photo, or HTML cards. New pushes can immediately select a card. Cached content works offline.

**Handoff for Hermes:** start with [docs/HERMES_HANDOFF.md](docs/HERMES_HANDOFF.md). On the existing Mac, the gateway and Android app are already installed. You can push content immediately without rebuilding, installing software, or enabling debugging.

## Working installation, as of October 12, 2026

| Component | Verified state |
| --- | --- |
| Frame | PF1007L, Allwinner A33, Android 6.0.1 / API 23, 1280 × 800 landscape |
| Original software | AiMOR 6.0.78; firmware `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113` |
| Custom app | Package `com.ian.frame`; installed and launches as HOME after reboot |
| Mac | User `ian`, host `ian-mini-m6`, LAN IP `192.168.1.128` |
| Gateway | `http://192.168.1.128:8765`, poll interval 3 seconds |
| Last observed frame IP | `192.168.1.34`; IP and randomized Wi-Fi MAC changed after reboot |
| Live service | `com.ian.hermes-frame`, a per-user macOS LaunchAgent |
| Last content update | Revision 3, photo card updated; frame polled afterward |
| Wireless ADB | Used successfully before reboot; port 5555 currently closed |
| Hermes runtime | Not located in process list, Spotlight, or common installation paths; no direct Hermes configuration changed |

The live gateway's data is authoritative. A clone does not contain its private credentials or saved photos. `status` confirms recent polling, not an on-screen rendering acknowledgement.

## Push from Hermes on this Mac

Use Hermes's shell/command execution tool. Python's standard library is enough:

```sh
/usr/bin/python3 -B "/Users/ian/Library/Application Support/HermesFrame/framectl.py" status
/usr/bin/python3 -B "/Users/ian/Library/Application Support/HermesFrame/framectl.py" text "Dinner plan" "Pasta at 7. Remember the basil."
/usr/bin/python3 -B "/Users/ian/Library/Application Support/HermesFrame/framectl.py" image "/absolute/path/photo.jpg" --id photo --title "A moment worth keeping"
/usr/bin/python3 -B "/Users/ian/Library/Application Support/HermesFrame/framectl.py" text "Weather" "Add your forecast here" --id weather --no-focus
```

- `text` updates card `hermes` by default. `image` defaults to card `image`.
- Reusing `--id` replaces that card; a new ID appends a swipeable card.
- A push selects its card by default. `--no-focus` preserves the current page.
- `--eyebrow` and `--accent '#RRGGBB'` customize text cards.
- `framectl.py remove CARD_ID` removes a custom card. Default `clock` and `hermes` cannot be removed.
- `framectl.py json FILE` accepts a structured payload; `json -` reads stdin.

For example:

```sh
/usr/bin/python3 -B "/Users/ian/Library/Application Support/HermesFrame/framectl.py" json /absolute/path/to/examples/note.json
```

```json
{
  "card": {
    "id": "note",
    "type": "text",
    "eyebrow": "HERMES",
    "title": "A useful thought",
    "body": "Your content here.",
    "accent": "#BBD7B2"
  },
  "focus": true
}
```

Supported types: `clock`, `text`, `image`, `html`. Images use the `image` field as a PNG/JPEG/WebP base64 data URI; the image command handles encoding. HTML uses the `html` field with inline CSS. JavaScript, file/content access, and external web resources are disabled. See [examples/dashboard.json](examples/dashboard.json).

Limits: 20 cards; 8 MiB per image; 12 MiB HTTP push payload; title 200 characters; body 16,000; eyebrow 80; HTML 100,000. The app also limits the complete state response to 2 MiB, so keep a multi-card HTML deck well below that. Images are stored separately and do not inflate the state JSON.

## Everyday operation

Swipe left/right or tap page indicators. Long-press **FRAME** at the top left to edit the source address or open **Original photos**. The custom app currently uses `http://192.168.1.128:8765`. Keep this Mac awake on the same LAN for new content; cached cards and the clock remain available otherwise. If the Mac's IP changes, update the source address in that menu. A DHCP reservation for the Mac is useful; do not assume the frame's randomized MAC will stay fixed.

Original AiMOR and its OTA updater remain installed, but were disabled to make the custom app the sole HOME launcher. **Original photos** uses the frame's existing `su` to re-enable both and launch AiMOR. This path was tested before the final reboot. Returning to AiMOR can affect which launcher starts afterward; see [wireless access and recovery](docs/WIRELESS_ACCESS.md).

## How it works

```text
Hermes shell tool → framectl.py → loopback POST /push → Mac gateway
                                                       ↑
                                frame polls /state + /media every 3s
                                ↓
                         native Android cards + private offline cache
```

`gateway.py` runs a threaded Python HTTP server, persists cards in `data/state.json`, and saves images by SHA-256 in `data/media/`. Writes use a separate token and require a loopback client. The frame reads state/media with a read-only token embedded at build time. The APK keeps its own state and image cache in app-private storage.

The gateway binds IPv4 `0.0.0.0:8765` for LAN reads. Transport is HTTP on the local network; bearer tokens and media are not encrypted in transit. `/health` is unauthenticated and returns only `{"ok":true}`. State/media require read authentication; `/push`, `/status`, and `/cards/ID` require local write authentication. Do not publish this service to the internet or include local token values in prompts, logs, or commits.

## Files and API

| File | Purpose |
| --- | --- |
| `android/src/com/ian/frame/MainActivity.java` | Native cards, gestures, polling, caching, recovery menu |
| `android/AndroidManifest.xml` | HOME/LAUNCHER intent, API 23, landscape activity |
| `gateway.py` | Persistent authenticated content API |
| `framectl.py` | Hermes-friendly text/image/JSON/status/remove client |
| `init_config.py` | New-install token generation; refuses to overwrite existing config |
| `deploy_gateway.py` | Copies gateway/client and registers the Mac login service |
| `build.py` | Direct Java → D8 → APK build; no Gradle or network dependency resolution |
| `test_gateway.py`, `test_config.py` | API and credential-preservation checks |
| `tools/` | Narrow, one-frame wireless debugging helper and protocol tests |
| `docs/` | Hermes handoff and device access/recovery notes |

| Endpoint | Authentication | Result |
| --- | --- | --- |
| `GET /health` | None | Minimal health response |
| `GET /state` | Read token | Deck and revision; records poll time/client |
| `GET /media/<sha256>.<ext>` | Read token | Stored image bytes |
| `GET /status` | Write token + loopback | `last_poll`, `client`, `revision`, `recently_connected` |
| `POST /push` | Write token + loopback | Upsert card; returns revision and card ID |
| `DELETE /cards/ID` | Write token + loopback | Remove custom card |

The header is `Authorization: Bearer <token>`. The installed CLI reads its private config automatically; using it avoids handling tokens manually. Success from `/push` means content was accepted and persisted. There is no frame receipt/render acknowledgement endpoint yet.

## Existing Mac: clone and continue development

Live files are at `~/Library/Application Support/HermesFrame/`; LaunchAgent is `~/Library/LaunchAgents/com.ian.hermes-frame.plist`. The original development checkout is:

```text
/Users/ian/Documents/Codex/2026-10-12/i-need-help-with-a-new/frame-project
```

After cloning into a new folder, preserve the current read/write tokens when rebuilding for this frame:

```sh
mkdir -p data
chmod 700 data
cp "$HOME/Library/Application Support/HermesFrame/data/config.json" data/config.json
chmod 600 data/config.json
```

Do not run `init_config.py` for the existing installation. Do not copy stale checkout state over the live data. `deploy_gateway.py` preserves an existing live `data/` directory and restarts an already registered service. Run it only when intentionally deploying gateway/client changes:

```sh
/usr/bin/python3 -B deploy_gateway.py
launchctl print "gui/$(id -u)/com.ian.hermes-frame"
/usr/bin/python3 -B "$HOME/Library/Application Support/HermesFrame/framectl.py" status
```

The service uses `/usr/bin/python3`; that interpreter was available and tested on this Mac. Logs: `gateway.log` and `gateway-error.log` in the live directory. Stop/start deliberately with `launchctl bootout` / `bootstrap`; avoid launching a second gateway on port 8765. Redeploying only gateway code does not require ADB.

## Fresh installation

This section is for a different device or a fresh gateway, not the working frame:

```sh
/usr/bin/python3 -B init_config.py --frame-url http://YOUR_MAC_LAN_IP:8765
/usr/bin/python3 -B gateway.py
```

The initializer creates ignored `data/config.json` with `port`, `frame_url`, `read_token`, and `push_token` and sets mode 600. Do not regenerate its tokens after installing the APK unless you also rebuild/reinstall the app. Run the gateway in a terminal for initial checks; stop it before running `deploy_gateway.py` to install the login service. The deploy script uses existing local config/data for a first install.

## Build the APK

Install a JDK 17 and Android SDK platform/build tools. [Android's build-tools documentation](https://developer.android.com/tools/releases/build-tools) describes the SDK layout; [Azul](https://www.azul.com/downloads/?version=java-17-lts&package=jdk) provides the JDK used here. Tested toolchain: Zulu 17.0.20.1 on Apple Silicon, Android build-tools 34.0.0 and platform `android-34-ext12`; app min/target SDK remains 23.

On the current Mac, downloaded tools are still in `/private/tmp/frame-wireless/build-tools`. The default build uses that tree and its bundled JDK. Temporary tools can disappear; SDK/JDK binaries are not in the repository.

```sh
/usr/bin/python3 -B build.py
```

For a normal durable Android SDK:

```sh
export FRAME_SDK_ROOT="$HOME/Library/Android/sdk"
export JAVA_HOME="/absolute/path/to/jdk/Contents/Home"
/usr/bin/python3 -B build.py
```

The build discovers `platforms/**/android.jar` and `build-tools/**/aapt2`, or the temporary tree's `android-platform` / `android-tools` layout. Keep one selected toolchain in that root for deterministic selection. Output is `android/build/frame.apk`; `apksigner verify` runs automatically.

**Keep the existing `android/build/frame.keystore` locally.** It is ignored, and a fresh clone creates a different development key. Updating the installed package requires the original key. Copy it from the original checkout's ignored build directory when continuing on this Mac. Uninstalling to bypass a signature mismatch deletes the app's private cache/settings; avoid that. The generated `BuildConfig.java` and APK contain the read token, so build output is excluded from Git.

Once wireless ADB has been re-enabled and verified, install with `adb -s CURRENT_FRAME_IP:5555 install -r android/build/frame.apk`. Full steps and current limitations are in [docs/WIRELESS_ACCESS.md](docs/WIRELESS_ACCESS.md).

## Validation

```sh
/usr/bin/python3 -B -m unittest test_gateway test_config
/usr/bin/python3 -B -m unittest discover -s tools -p 'test_*.py'
/usr/bin/python3 -B tools/frame_adb_listener.py --dry-run
```

Tests cover API authentication, focus/upsert/persistence, rejection without state mutation, image byte round-trip, credential file permissions/non-overwrite, protocol fragmentation, malformed messages, heartbeat handling, login gating, and peer restriction. Loopback/socket tests need local networking permitted.

Device checks already performed: native app launch, live text push, swipe navigation, Original photos recovery, signed APK verification, and startup after reboot. The latest photo update was accepted and the frame subsequently polled; it has not been visually confirmed through a new screenshot since ADB closed.

## Follow-up work

1. Locate/configure Hermes's actual runtime, then expose the installed CLI as its frame tool or skill.
2. Decide the desired default content (weather, calendar, reminders, family photos, or another deck).
3. Add render acknowledgements and user-friendly delivery errors if stronger confirmation is needed.
4. Add image orientation as a card/display option, and validate on the frame.
5. Add bounded image-cache/media cleanup; currently old images remain on disk.
6. Consider encrypted/authenticated transport and durable addressing if deployment extends beyond this trusted LAN.

Personal photos, live tokens, router credentials, signing keys, binary backups, generated APKs, and local previews are excluded. Verified local boot/recovery backups are limited partition backups, not a complete device image. No boot/system partition was flashed.
