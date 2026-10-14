# Hermes handoff

## User's intended outcome

Keep useful default content on the photo frame, swipe among cards, and let the Hermes agent running on the user's machine push new content on demand. The custom Android launcher and push gateway are already operational. The remaining integration is to connect the actual Hermes runtime to the installed client and agree on the default content.

Repository: https://github.com/ianmabie/frameBot

## October 14: cookbook reviewed; physical deployment pending

Final parent verification supersedes historical sandbox limitations below: independent review passed; 54 root tests, 4 protocol tests, 13 production-cache regressions plus executable navigation passed; final API 23 unsigned APK rebuilt successfully. Exactly 50 actual recipes rendered and imported/read back through a local test gateway, verifying all 100 asset references without changing its weekly deck. User authorized merging and installation plus necessary temporary DNS/debugging changes, restored afterward. Owner signing access and router authentication remain pending; user is resolving them. Do not touch the handed-off browser/session until the user returns. No production installation or DNS change has occurred.

The cookbook source implementation adds Photos / This Week / Cookbook navigation and an independent offline collection of up to 50 recipes. Cookbook import never changes the 20-card deck or approves a weekly menu. `approved_week.py` and its acceptance requirements remain unchanged. Parent reported frame `192.168.1.35` and deck revision 33; older `.34` observations below are historical. No live status query or deployment succeeded in this sandbox.

Read [COOKBOOK_DEPLOYMENT.md](COOKBOOK_DEPLOYMENT.md) and [the implementation report](../COOKBOOK_IMPLEMENTATION_REPORT.md) before using the new source. This task uses synthetic fixtures and does not poll the separate catalog. No runtime recipes/media/secrets are included. Parent reports **54 root tests + 4 protocol tests + 9 executable Java cache regressions passed**, and a **real API 23 unsigned APK build passed**. The final independent cache race fix serializes complete deck/cookbook download-to-index-save transactions with trimming across Activity instances and adds four production-method concurrency/lifecycle regressions. Production and harness type checking against API 23 passed; protocol tests reran with 4 passes. Running the expanded Java suite was blocked at new scratch directory creation, so parent must rerun it and rebuild the unsigned APK for this final patch. Signing, device installation and remote merge remain unperformed; no commit or push occurred here. The build refuses to generate a signing key.

Owner-only deployment uses Ian's original key/config directly from his owner session, with parent review and current authorization first. Do not access/copy Ian's private files through shell-e. Do not use sudo, change routers/partitions, uninstall the app or re-enable wireless debugging without the owner's current confirmation. The original-app escape remains in the implementation and needs owner device verification after a correctly signed update.

## Update: shared profiles and open LAN pushes

Ian explicitly requested very open permissions: any LAN device should push without credentials. The gateway now admits token-free `POST /push` and `GET /status` from `192.168.1.0/24` and loopback. `/Users/Shared/HermesFrameClient/framectl.py` is readable/executable through Python from every local profile and defaults to the local gateway. For shell-e, use this shared path instead of Ian's private Library path. The client code contains no credentials. A separate ACL-protected delete-only credential is now available to shell-e. Do not run the old staged sudo installer.

Remote Hermes on the home server can use the cloned CLI with `--url http://192.168.1.128:8765` or direct JSON POST, provided its source address is on the admitted LAN. Existing shell-e SSH can also run the shared client on the mini. For meal-plan updates, use stable menu/recipe card IDs and `focus:false` to preserve the current photo selection. See [LAN_PUSH.md](LAN_PUSH.md).

Default token-authenticated behavior remains available for fresh installs; this existing service's private config explicitly enables public mode. Any admitted device can overwrite a card by ID. Frame reads and deletion remain authenticated. For deletion, shell-e should run `/usr/bin/python3 -B /Users/Shared/HermesFrameClient/framectl.py remove CARD_ID` through its existing local/SSH shell; the client automatically loads its scoped credential on loopback. No owner token or sudo is needed. The clock is protected; the Hermes test card can be removed. See LAN_PUSH.md for grant/revocation and limits. The service must remain running under Ian while profiles switch.

## Update: combined previews and acceptance-gated weeks

The handed-off photo/recipe preview state consists of the photo pair plus three combined recipe cards with photo left and full ingredients/method right. Obsolete standalone recipe samples were removed. This is the provided preview state, not a new live verification or publication by this implementation. Personal photos, recipe sources, generated previews, and personal content remain outside git.

Weekly drafts are **NOT published until Ian accepts the specific menu**. After that acceptance, replace the prior recipe cards while preserving photos and the clock. Use the portable `render_cards.py` commands and `approved_week.py` workflow documented in [README.md](../README.md#no-scroll-previews-and-accepted-weekly-replacement). Rendering uses caller-supplied paths/recipe JSON and fixed 1280 × 800 layouts; overflow fails rather than shrinking text. Portrait pairs are EXIF-correct and uncropped; image titles are blank.

The weekly manifest contains stable `dinner-week` and `recipe-mon..sun` image IDs, with fewer recipe IDs permitted for repeated dinners. Supply an explicit acceptance record bound to the week and SHA-256 of the exact manifest and all image content, with a required nonempty `source_message` string citing Ian's actual accepting conversation message. Optional session metadata cannot replace that citation. Default execution is a dry-run with no client calls or ledger changes; only `--apply` with matching acceptance writes. It runs the existing SSH shared framectl as `shell-e@ian-mini-m6.local`, with argv/stdin and no publisher credential handling. Optional `--identity-file /private/path/ssh-identity` passes a caller-supplied path to `ssh -i` without reading the file; omit it to use SSH's configured identities.

Validate all rendered images before sending. Overwrite stable cards with `focus:false` first. After all new writes succeed, remove only prior managed IDs from the persisted private publisher ledger that are absent this week. The first successful approved publication also removes exactly the three legacy combined previews `sample-recipe-1..3`; it never removes photos/clock or scans for similarly named cards. Preserve the ledger across weeks and run one publisher at a time. A partial failure records completed writes and the uncertain current operation, stops immediately, and requires manual reconciliation before a new apply. Publication is not atomic and must not be blindly repeated.

Check returned IDs and a subsequent frame poll. Accepted/polled is not rendered/seen; the API still has no rendering acknowledgement. A successful publication with unverified later polling exits 2 and must be checked with `status`, not republished. No actual frame pushes, deployment, app/gateway/API/authentication changes, commit, or git push occurred in this implementation.

## First action on the existing Mac

Run this using your shell tool:

```sh
/usr/bin/python3 -B "/Users/ian/Library/Application Support/HermesFrame/framectl.py" status
```

The gateway should report `recently_connected: true`, a recent `last_poll`, and the current frame IP. The latest observation after the LAN access change was `192.168.1.34`, revision 5. IPs can change. If connected, you can immediately send content using this client. No USB, ADB, install, token generation, or router changes are needed for normal pushes.

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

No `hermes` executable, `.hermes` directory, Hermes process, Spotlight match, or install in common Mac locations was found. No Hermes tool/skill was configured and no runtime was installed. The similarly named `HermesFrame` folder is this gateway, not the agent. If this handoff is being read by Hermes elsewhere, local push endpoints must be executed on `ian-mini-m6` as the owning user; remote token-free pushes to port 8765 now work from the admitted LAN. Other networks require existing authorized remote execution on this Mac or a separately requested change to the admitted networks.

## Development sequence

1. Read README.md and check live status.
2. Push requested content with the existing client before considering app changes.
3. Build as the owner using `build.py --config /owner/live/data/config.json --keystore /owner/original/project/android/build/frame.keystore`. Do not copy/read owner private files through shell-e or regenerate tokens/key.
4. Run API/config/protocol tests. Build/verify the APK if Android code changes.
5. Deploy gateway-only changes with deploy_gateway.py; it preserves live data and restarts the LaunchAgent.
6. Android changes require re-enabling wireless ADB: see WIRELESS_ACCESS.md. Keep original AiMOR/OTA installed, and preserve the tested Original photos escape path.
7. Confirm frame behavior using a screenshot or the user when possible. Distinguish accepted/polled from rendered/seen.

The initial repo snapshot includes a portable SDK/JDK build override, fresh-install credential initializer, and repeatable gateway redeploy support. Those source refinements were tested locally; the earlier publishing pass did not redeploy the gateway. The open-LAN change was subsequently deployed to the existing service while preserving its saved data and credentials. The installed app/gateway continue to serve the working deck.

## Known limitations

- Landscape app layout; image cards fit within the existing header/footer rather than edge-to-edge.
- The photo rotation has been pushed, but no post-reboot screenshot confirms appearance because ADB is closed.
- Source URL can be changed on-device, but the read token is embedded in the APK.
- HTTP on the LAN; no TLS or render acknowledgements. Public-push mode uses admitted source subnets, with no per-device identity; frame reads and deletion retain bearer authentication.
- State response limit 2 MiB and fixed-size typography; avoid giant HTML decks/long titles.
- The deployed old app still retains old images. Pending cookbook source prunes Android disk cache and confines decoded bitmaps to the visible screen; owner deployment and device validation are outstanding. Gateway unreferenced media still needs owner-controlled cleanup.
- The actual physical storage is about 15.75 GB despite the listing advertising 32 GB.
- Boot/recovery backups do not cover userdata/system and are not a general restore image.

User has authorized this custom-frame project, wireless debugging, app installation, pushing the provided photo, and creating/uploading this repository. Router credentials were supplied in the original conversation and are not stored in this repo. Obtain them from the user if access is needed later; do not search or publish unrelated credentials.
