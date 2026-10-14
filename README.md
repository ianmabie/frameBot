# Hermes Frame

A working custom launcher for a humblestead PF1007L photo frame, plus a persistent Mac gateway that lets Hermes push content. The frame has a default clock and agent card; swipe between those and added text, photo, or HTML cards. New pushes can immediately select a card. Cached content works offline.

**Handoff for Hermes:** start with [docs/HERMES_HANDOFF.md](docs/HERMES_HANDOFF.md). On the existing Mac, the gateway and Android app are already installed. You can push content immediately without rebuilding, installing software, or enabling debugging.

## Open LAN pushes and other Mac profiles

At Ian's request, token-free pushes are enabled for `192.168.1.0/24` and loopback. From any Mac profile, use `/usr/bin/python3 -B /Users/Shared/HermesFrameClient/framectl.py status` or its text/image/JSON commands. From another LAN device, use `POST http://192.168.1.128:8765/push` without an Authorization header, or `framectl.py --url http://192.168.1.128:8765 ...` from a clone. See [docs/LAN_PUSH.md](docs/LAN_PUSH.md) for commands and configuration. No token copies or sudo installer are needed for shell-e.

Any admitted device can add or overwrite cards in this mode. The gateway checks the actual socket source IP against configured CIDRs. Saved frame reads remain authenticated. Deletion requires loopback plus an owner token or a granted delete-only profile token; `shell-e` now has a grant and can use the shared client’s `remove CARD_ID` command. The owner-run service must remain running while profiles switch.

## Working installation, as of October 13, 2026

| Component | Verified state |
| --- | --- |
| Frame | PF1007L, Allwinner A33, Android 6.0.1 / API 23, 1280 × 800 landscape |
| Original software | AiMOR 6.0.78; firmware `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113` |
| Custom app | Package `com.ian.frame`; installed and launches as HOME after reboot |
| Mac | User `ian`, host `ian-mini-m6`, LAN IP `192.168.1.128` |
| Gateway | `http://192.168.1.128:8765`, poll interval 3 seconds |
| Last reported frame IP | `192.168.1.35`, deck revision 33, reported by parent October 14; not queried by this implementation. `.34` is stale |
| Live service | `com.ian.hermes-frame`, a per-user macOS LaunchAgent |
| Latest handed-off content | Photo pair and three combined recipe preview cards; obsolete standalone samples removed. Not queried live during this implementation |
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
- `framectl.py remove CARD_ID` removes a custom card. The default `clock` cannot be removed; `hermes` can be removed.
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

## No-scroll previews and accepted weekly replacement

The handed-off preview state is a paired photo card and three combined recipe previews, each with its photo, ingredients, and method on one landscape image. Obsolete standalone recipe samples were removed. These are previews, not an accepted weekly menu. This implementation did not query or modify the live frame.

`render_cards.py` provides portable `collage` and `recipe` commands. Install Pillow, reportlab, and PyMuPDF into a Python environment (see `requirements-render.txt`). Pass your own paths; no personal images, names, meal-plan sources, or generated media are bundled. Keep inputs, outputs, manifests, acceptance records, and publisher ledgers outside git, or under ignored `local-assets/`.

```sh
PYTHON=/absolute/path/to/python-with-render-deps
"$PYTHON" -B render_cards.py collage /private/path/left.jpg /private/path/right.jpg \
  --output /private/path/photo-pair.png --manifest /private/path/photo-pair.json
"$PYTHON" -B render_cards.py recipe examples/recipe.json --photo /private/path/food.jpg \
  --id recipe-mon --week 2026-10-19 --output /private/path/recipe-mon.png \
  --manifest /private/path/recipe-mon.json
```

Both outputs are 1280 × 800. Collages apply EXIF orientation and contain both entire portraits without cropping. Recipe photos occupy the left column; all ingredients and numbered steps occupy the right at fixed font sizes. Text is treated literally. Overflow or unsupported font glyphs fail clearly before saving a new image; shorten/split the content rather than shrinking type. Recipe JSON requires `title`, `ingredients` (text or a list), and `steps` (a list); optional fields are `photo`, `meta`, `eyebrow`, `note`, and `credit`. A JSON `photo` path resolves relative to its JSON file; `--photo` overrides it. See the synthetic [example](examples/recipe.json). Image card payloads have a blank title and `focus:false`.

Assemble a weekly rendered manifest with a caller-prepared 1280 × 800 menu image and one recipe image per unique recipe. IDs are stable: `dinner-week` and `recipe-mon` through `recipe-sun`; a repeated recipe can use its first day's ID, so fewer than seven recipe cards are fine. List all seven dinners in the menu image, referring to shared recipe cards as needed. A photo collage belongs to the separate photo workflow, never this weekly manifest.

```json
{
  "week": "2026-10-19",
  "cards": [
    {"id": "dinner-week", "path": "menu.png", "title": "", "focus": false},
    {"id": "recipe-mon", "path": "recipe-mon.png", "title": "", "focus": false}
  ]
}
```

Image paths resolve relative to the manifest. All files are read, decoded, and validated before any client call. First review the actual menu and images, then dry-run:

```sh
"$PYTHON" -B approved_week.py /private/path/week.json --ledger /private/path/publisher-ledger.json
```

Weekly drafts are **not published until Ian accepts the specific menu**. After acceptance, the operator supplies an explicit record containing the dry-run digest:

```json
{
  "approved": true,
  "accepted_by": "Ian",
  "week": "2026-10-19",
  "sha256": "DIGEST_FROM_DRY_RUN",
  "source_message": "ACTUAL_CONVERSATION_REFERENCE / ACCEPTING_MESSAGE_REFERENCE: Ian's acceptance of this exact menu"
}
```

This is a placeholder example, not an approval. `source_message` is required and must be a nonempty string citing the actual conversation message in which Ian accepted this exact menu and rendered content; replace the placeholder with that message's reference. Optional session metadata (for example, `session_id`) may accompany it but cannot substitute for `source_message`. The tool rejects missing, blank, or non-string citations; the operator must verify the cited message's acceptance.

The tool does not create acceptance records or infer acceptance. Its SHA-256 covers length-prefixed exact manifest bytes followed by length-prefixed image bytes in manifest order. Editing any manifest byte or image invalidates approval. The record is an operator-provided assertion of Ian's acceptance, not an identity/signature verification system.

```sh
# Still a dry-run; no SSH, writes, or ledger mutation:
"$PYTHON" -B approved_week.py /private/path/week.json --ledger /private/path/publisher-ledger.json \
  --approval /private/path/accepted.json
# Only run after Ian has accepted that exact menu and rendered content:
"$PYTHON" -B approved_week.py /private/path/week.json --ledger /private/path/publisher-ledger.json \
  --approval /private/path/accepted.json --identity-file /private/path/ssh-identity --apply
```

Apply uses subprocess argv and JSON stdin through SSH as `shell-e@ian-mini-m6.local` (`--host shell-e@HOST` can select an existing SSH hostname), invoking `/usr/bin/python3 -B /Users/Shared/HermesFrameClient/framectl.py`. Optional `--identity-file /private/path/ssh-identity` passes the caller's path as a separate `ssh -i` argument; omit it to use SSH's configured identity selection. The publisher does not read the identity file. The existing client handles its own permissions; the publisher never loads or copies credentials. No app, gateway, API, or authentication changes are needed.

Every new card is sent with `focus:false`, and its returned ID/revision is checked. Only after all writes succeed does cleanup remove previous managed IDs recorded in the persistent publisher ledger but absent from the new manifest. On the first successful approved publication it also removes exactly `sample-recipe-1`, `sample-recipe-2`, and `sample-recipe-3` (already absent is harmless). Photos, the clock, and all untracked IDs are preserved. Never delete the prior week before uploading its replacement. The existing 20-card limit still applies; if there is no room, publication stops without pre-deleting cards.

Publication is a sequence of acknowledged writes, not an atomic transaction. The private ledger records completed writes/removals and the current possibly uncertain operation. Any partial failure stops immediately and blocks another apply until the operator manually reconciles the frame and ledger; do not delete the ledger and blindly retry. After reconciliation, preserve the union of known managed IDs, set `legacy_removed` according to the actual cleanup, and clear the failed `attempt` only when deliberately authorizing a new attempt. Use one publisher process per ledger. Keep this ledger across weeks; it is the sole ownership history used for cleanup.

After successful writes/cleanup, the publisher checks for a later `last_poll` and a revision at least as new as the final acknowledgement. This verifies polling, **not rendering**. Apply exits 2 if publication succeeded but a later poll was not verified; use the existing client's `status` later, without resending. Exact already-published manifests are refused to prevent repeats. Dry-run exits 0; invalid approvals and partial publications exit 1.

## Everyday operation

Swipe left/right or tap page indicators. Long-press **FRAME** at the top left to edit the source address or open **Original photos**. The custom app currently uses `http://192.168.1.128:8765`. Keep this Mac awake on the same LAN for new content; cached cards and the clock remain available otherwise. If the Mac's IP changes, update the source address in that menu. A DHCP reservation for the Mac is useful; do not assume the frame's randomized MAC will stay fixed.

Original AiMOR and its OTA updater remain installed, but were disabled to make the custom app the sole HOME launcher. **Original photos** uses the frame's existing `su` to re-enable both and launch AiMOR. This path was tested before the final reboot. Returning to AiMOR can affect which launcher starts afterward; see [wireless access and recovery](docs/WIRELESS_ACCESS.md).

## Cookbook library (source implementation; awaiting owner deployment)

The native landscape app has visible **Photos / This Week / Cookbook** navigation. Photos retains the clock, photos, notes and preview cards; This Week selects existing `dinner-week` and `recipe-mon..sun` IDs. Those IDs and the deck remain unchanged. Cookbook is a separate collection of up to 50 recipes and never consumes the deck's 20-card allowance. Choosing a cookbook recipe opens its detail; it does not add a weekly dinner or approve a menu. The weekly acceptance workflow above remains required.

Cookbook offers a category selector, eight photo/title tiles per page, page buttons and horizontal swipes. Recipe detail displays the renderer's complete 1280 × 800 photo-left/ingredients-and-method-right image without scrolling, with Library and previous/next buttons. Category, minutes, servings, note, photo credit and the representative-photo label are rendered into each detail. Source URLs and adaptation metadata remain in the offline index; the app never loads those websites. The **FRAME** long-press / **Original photos** escape remains available in every tab. Photo/weekly selections are retained across tab changes and saved for restart; the startup tab remains Photos.

Supply your own private catalog as either a list or `{"recipes": [...]}`. The render command requires **exactly 50** unique recipes, each with `id`, `title`, `category`, `minutes` (estimated integer 10–35), `servings` (3), `ingredients` (1–18 quantified strings), `steps` (3–5 strings), `note`, `photo` (relative path under `photos/`), `photo_credit`, `photo_source_url`, `photo_representative` (true), `source_urls` (1–10 HTTP/HTTPS attribution URLs), and `original_or_adapted` (nonempty attribution/adaptation description). Each ingredient must include a numeric quantity; express salt/oil/seasonings explicitly too. Bounds are in [cookbook.py](cookbook.py). Typography stays fixed: overflow, unsupported glyphs, excessive asset size or credit overflow fail with the recipe ID. Review actual images before any import.

```sh
PYTHON=/absolute/path/to/python-with-render-deps
"$PYTHON" -B render_cards.py cookbook /private/path/catalog.json \
  --output /private/path/cookbook-rendered-v1
# Dry-run: validates every manifest entry and image before any network calls.
"$PYTHON" -B framectl.py --url http://192.168.1.128:8765 cookbook-import \
  /private/path/cookbook-rendered-v1/manifest.json
# After source/content review and owner deployment, when publication is authorized:
"$PYTHON" -B framectl.py --url http://192.168.1.128:8765 cookbook-import \
  /private/path/cookbook-rendered-v1/manifest.json --apply
```

The output directory must be new. Rendering stages the entire bundle before publishing the directory; any failure removes staging and leaves previous bundles intact. Detail PNGs and 384 × 200 photo thumbnails are named by SHA-256. The import client validates all files first, uploads one file at a time, checks returned paths, then sends one manifest replacement. Upload failure leaves the old cookbook index usable; successful uploads may leave unreferenced assets. An identical retry is safe for the cookbook. It never calls `/push` or `/cards`, and never reads a weekly approval/ledger. The supplied catalog will be prepared separately; no runtime recipes/media are bundled in Git.

The app saves the new cookbook index only after downloading and checking every asset's hash and dimensions. Failed transfers retain the prior complete offline library. Network loss keeps Photos, This Week, category filtering, paged thumbnails, detail swipes and Library navigation available from saved files. First sync can take several minutes; the existing library remains visible meanwhile. The clock works offline without a download. The app polls the cookbook every 30 seconds alongside the existing 3-second deck polling; cookbook sync failures do not discard deck updates. Old cached files and interrupted transfers are pruned against committed indices. With current limits, retained files are at most 310 MiB; one staged update can temporarily use up to 470 MiB, below the 480 MiB cache guard. The display decodes only the current eight thumbnails or one detail/card, uses sampled RGB565 bitmaps, drops detached screen references, and never preloads 50 full-size bitmaps.

| Endpoint | Guard | Behavior |
| --- | --- | --- |
| `GET /cookbook` | Existing read token | Offline index, stable content-derived revision |
| `GET /cookbook/assets/<sha256>.png` | Existing read token | Immutable PNG bytes |
| `POST /cookbook/assets` | Existing push-token/loopback or explicitly admitted LAN | `{image: "data:image/png;base64,..."}`; validates bounded RGB/RGBA PNG, returns `asset_path` |
| `POST /cookbook/import` | Same write guard | `{version: 1, recipes: [...]}`; 1–50 entries; every entry includes `thumbnail_path`, `detail_path` and catalog metadata; validates all referenced assets, atomically replaces `data/cookbook.json` |

Manifest JSON is limited to 512 KiB, PNGs to 1.5 MiB with exact thumbnail/detail dimensions. `/status` also reports `cookbook_revision`. Collection revisions are canonical SHA-256 values independent of the deck revision; formatting/key ordering and unchanged imports do not create revisions. The gateway/client require only Python's standard library. Deploy now includes the cookbook modules in both the owner gateway and shared client directory. Authentication, admitted subnets, delete-only scope, and network exposure are unchanged. There is no rendering acknowledgement; an accepted import is not a visual confirmation. See [docs/COOKBOOK_DEPLOYMENT.md](docs/COOKBOOK_DEPLOYMENT.md) and [COOKBOOK_IMPLEMENTATION_REPORT.md](COOKBOOK_IMPLEMENTATION_REPORT.md).

## How it works

```text
Hermes shell tool → framectl.py → loopback POST /push → Mac gateway
                                                       ↑
                                frame polls /state + /media every 3s
                                ↓
                         native Android cards + private offline cache
```

`gateway.py` runs a threaded Python HTTP server, persists cards in `data/state.json`, and saves images by SHA-256 in `data/media/`. Writes normally use a separate token and loopback client; the explicitly enabled public-push mode also accepts token-free LAN and loopback pushes. The frame reads state/media with a read-only token embedded at build time. The APK keeps its own state and image cache in app-private storage.

The gateway binds IPv4 `0.0.0.0:8765` for LAN reads. Transport is HTTP on the local network; bearer tokens and media are not encrypted in transit. `/health` is unauthenticated and returns only `{"ok":true}`. State/media require read authentication. `/push` and `/status` allow token-free configured LAN access when public-push mode is enabled; `/cards/ID` requires a local owner or delete-only profile credential. Do not publish this service to the internet or include local token values in prompts, logs, or commits.

## Files and API

| File | Purpose |
| --- | --- |
| `android/src/com/ian/frame/MainActivity.java` | Native cards, gestures, polling, caching, recovery menu |
| `android/AndroidManifest.xml` | HOME/LAUNCHER intent, API 23, landscape activity |
| `gateway.py` | Persistent authenticated content API |
| `framectl.py` | Hermes-friendly text/image/JSON/status/remove client |
| `render_cards.py` | Portable EXIF-correct photo pairs and fixed-layout recipe images |
| `approved_week.py` | Dry-run-first, acceptance-bound weekly publication and ledger cleanup |
| `test_cards.py` | Synthetic renderer and subprocess fake-client publication tests |
| `grant_delete.py` | Owner-run local profile deletion grant/revocation with named-user ACL |
| `init_config.py` | New-install token generation; refuses to overwrite existing config |
| `deploy_gateway.py` | Copies gateway/client, installs shared client, and registers the Mac login service |
| `build.py` | Direct Java → D8 → APK build; no Gradle or network dependency resolution |
| `test_gateway.py`, `test_config.py` | API and credential-preservation checks |
| `tools/` | Narrow, one-frame wireless debugging helper and protocol tests |
| `docs/` | Hermes handoff and device access/recovery notes |

| Endpoint | Authentication | Result |
| --- | --- | --- |
| `GET /health` | None | Minimal health response |
| `GET /state` | Read token | Deck and revision; records poll time/client |
| `GET /media/<sha256>.<ext>` | Read token | Stored image bytes |
| `GET /status` | Configured LAN in public mode, or write token + loopback | `last_poll`, `client`, `revision`, `recently_connected` |
| `POST /push` | Configured LAN in public mode, or write token + loopback | Upsert card; returns revision and card ID |
| `DELETE /cards/ID` | Owner or granted delete-only token + loopback | Remove any card except clock |

In authenticated mode the header is `Authorization: Bearer <token>`. Token-free public LAN pushes omit it. The owner-installed CLI reads its private config automatically; using it avoids handling tokens manually. Success from `/push` means content was accepted and persisted. There is no frame receipt/render acknowledgement endpoint yet.

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

**Use the existing owner signing key.** `build.py` never generates a key and refuses a signed build when the original key is missing. Use `--keystore /owner/original/project/android/build/frame.keystore` and `--config /owner/live/data/config.json` from the owner's session; do not copy/read owner secrets through shell-e. The default ignored paths still work in the original project. `--unsigned` creates `android/build/aligned.apk` for source review when SDK/config are available; it cannot update the existing frame. Signed builds verify and print certificate fingerprints, which the owner must compare with the previously verified installed build. Uninstalling to bypass a mismatch deletes settings/cache; avoid it. Build output and generated `BuildConfig.java` contain the read token and stay excluded from Git.

Once wireless ADB has been re-enabled and verified, install with `adb -s CURRENT_FRAME_IP:5555 install -r android/build/frame.apk`. Full steps and current limitations are in [docs/WIRELESS_ACCESS.md](docs/WIRELESS_ACCESS.md).

## Validation

```sh
"$PYTHON" -B -m unittest discover -p 'test_*.py'
/usr/bin/python3 -B -m unittest discover -s tools -p 'test_*.py'
/usr/bin/python3 -B tools/frame_adb_listener.py --dry-run
```

Use the rendering-dependency Python above for the full suite. Card tests use temporary generated solid images and a fake subprocess client; they never contact SSH or the frame. Tests cover rendering overflow, uncropped EXIF photo pairs, acceptance mismatch, dry-run isolation, preservation, partial failures, weekly cleanup, later polling, API authentication, delete-only scope and revocation, shared-client profile selection and credential routing, clock protection, focus/upsert/persistence, rejection without state mutation, image byte round-trip, credential file permissions/non-overwrite, protocol fragmentation, malformed messages, heartbeat handling, login gating, and peer restriction. Loopback/socket tests need local networking permitted.

Device checks already performed: native app launch, live text push, swipe navigation, Original photos recovery, signed APK verification, and startup after reboot. The latest photo update was accepted and the frame subsequently polled; it has not been visually confirmed through a new screenshot since ADB closed.

## Follow-up work

1. Locate/configure Hermes's actual runtime, then expose the installed CLI as its frame tool or skill.
2. Decide the desired default content (weather, calendar, reminders, family photos, or another deck).
3. Add render acknowledgements and user-friendly delivery errors if stronger confirmation is needed.
4. Add image orientation as a card/display option, and validate on the frame.
5. Add owner-controlled gateway media cleanup; the Android cache now prunes obsolete images, while unreferenced gateway uploads remain on disk.
6. Consider encrypted transport and durable addressing if deployment extends beyond this trusted LAN; open LAN push mode is an explicit user preference.

Personal photos, live tokens, router credentials, signing keys, binary backups, generated APKs, and local previews are excluded. Verified local boot/recovery backups are limited partition backups, not a complete device image. No boot/system partition was flashed.
