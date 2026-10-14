# Cookbook implementation report

## Final parent verification — October 14, 2026

The final transaction-race patch was independently approved with no security or logic findings. Parent reran **54 root tests, 4 protocol tests, all 13 executable production-cache regressions and the navigation harness** successfully, then rebuilt the real API 23 unsigned APK successfully. All 50 actual catalog recipes rendered; local HTTP import/readback verified all 100 detail/thumbnail references and unchanged weekly deck. These final results supersede the historical sandbox blockers below. Signing, physical installation, router changes and device visual/offline checks have not occurred; original-key owner access remains required. Runtime catalog/media and APKs are excluded from Git.

Date: October 14, 2026. Current review task is on `cookbook-tab` (parent-supplied branch context). Source changes remain local for review. No commit, push, live deployment, live content change, router change, wireless debugging enablement, sudo, partition operation or signing-key generation occurred.

## Delivered source

| Path | Implemented behavior |
| --- | --- |
| `cookbook.py` | Shared bounded schema; unique IDs; 1–50 entries independent of deck; quantified ingredients; 3–5 complete steps; estimated 10–35 minutes and three servings; photo/source/adaptation attribution; representative-photo requirement; canonical stable collection SHA-256; strict fixed-size PNG validation including CRC/decompressed scanlines |
| `gateway.py` | Authenticated cookbook index/media reads; existing admitted-LAN/owner-loopback write guard for uploads/import; prevalidate all manifest entries and referenced assets; fsync staged data then atomic index replacement under lock; unchanged deck state/revision and 20-card limit; identical-import idempotence; upload repairs corrupt content-addressed files |
| `cookbook_import.py`, `framectl.py` | Dry-run-first bundle import; validate every entry/image before HTTP; upload one asset at a time; check returned path/revision; replace only cookbook index; no `/push`, deletion, approval inference or credential copying; redirect rejection retained |
| `render_cards.py` | Exactly-50 catalog renderer; existing combined no-scroll landscape recipe layout; photo thumbnails; category/estimated time/servings/note/credit/representative label; fixed type; overflow errors identify recipe; all-or-nothing staged bundle directory; all metadata retained in manifest |
| `android/src/com/ian/frame/MainActivity.java` | Visible Photos / This Week / Cookbook navigation; photo home/selection preservation; unchanged stable weekly IDs selected under This Week; category filter; 4 × 2 grid/paging/swipe; recipe choice; single-image detail with complete photo-left/text-right content; Library return/detail swipes; existing FRAME long-press and Original photos escape; offline collection caching separate from deck |
| `android/src/com/ian/frame/LibraryNavigation.java` | Pure tested category/page/recipe-selection state; weekly ID classification; safe empty/removal/wrap behavior |
| `android/src/com/ian/frame/OfflineAssets.java` | Hash verification, safe asset paths, interrupted/obsolete image-cache pruning, explicit size guard; no bitmap preloading |
| `android/AndroidManifest.xml` | Version 1.1/code 2; existing landscape/API 23/HOME configuration and permissions retained |
| `build.py` | Existing-key-only signing; no key generation; owner config/key path arguments; unsigned review option when SDK exists; signature verification and fingerprint output for owner comparison |
| `deploy_gateway.py` | Includes both cookbook modules in owner gateway and shared client; retains existing data/credentials |
| `test_cookbook.py`, `tests/java/com/ian/frame/CookbookLogicTest.java`, `test_gateway.py` | Synthetic renderer/schema/API/client/failure/isolation/auth tests; production Java navigation/offline-cache checks; actual HTTP integration test added for parent rerun |
| `README.md`, `docs/HERMES_HANDOFF.md`, `docs/WIRELESS_ACCESS.md`, `docs/COOKBOOK_DEPLOYMENT.md` | Updated workflow, API, bounds, owner deployment/build/signing/access constraints and exact rerun commands |

`approved_week.py` is unchanged. It still requires acceptance of the specific manifest/images with the actual accepting-message citation before apply. Cookbook selection/import never publishes a weekly dinner. The Store's existing 20-card cap is unchanged, and tests fill it before importing 50 cookbook recipes. Current deck cards, photos and saved weekly recipe assets were never read or modified by this task.

## Cache and publication behavior

The gateway stores `data/cookbook.json` separately from `data/state.json`, and cookbook PNGs in `data/cookbook-assets/`. The stable revision is derived from canonical manifest content; same content/key reordering does not increment it or the deck revision. Every referenced image is checked before authoritative replacement. Read/index/download endpoints use the existing read token. Write endpoints use the existing push guard, including the already authorized source-subnet mode; delete-only tokens retain their existing scope. No internet endpoint, source-URL fetch, new credential or wider network admission was added.

Android caches index/thumbnails/details in private files. It verifies all new assets before fsync/renaming the new index; failed sync leaves the previous complete library. It displays at most eight thumbnails or one detail/card, sampling to bounded dimensions with RGB565 preferred. Detached view/bitmap references are dropped rather than explicitly recycled while the Android render thread might still use them. No 50-image decode or memory LRU preload exists. At allowed sizes, one 19-image deck and one 50-recipe cookbook contain up to 302 MiB of image files. Deferred cleanup can leave two deck and two cookbook generations (604 MiB) in play, so generation arithmetic alone does not enforce the limit. The cache now admits every image or index staging operation against the combined 480 MiB disk budget before any download/write. Accounting includes committed images/indices and image/index `.tmp` files. The shared `OfflineAssets.class` lock spans each complete collection's asset verification/download through durable index save, across Activity instances; trim loads both keep sets and deletes under that same lock. Each image reserves its full per-file maximum (8 MiB deck / 1.5 MiB cookbook), and indices reserve their encoded byte length. Downloads stream through one 8192-byte RAM buffer with a per-file check before each write; no extra disk download buffer exists. Budget failure leaves authoritative indices and existing referenced assets in place. Pruning runs before and after synchronization and removes interrupted/unreferenced staging while retaining both indices' assets. The gateway retains unreferenced uploaded assets; later owner-controlled gateway cleanup is still a follow-up.

## Blocking review fixes (October 14, 2026)

The previous two cache blockers and the final independent P2 transaction/trim race are addressed below. The final follow-up changes only Android transaction/cancellation logic, production-method regressions and validation/deployment documentation. Stable weekly IDs, deck/API/auth contracts, gateway, catalog, renderer, Original photos behavior, and polling order remain unchanged. No commit, push, live change, owner credential access or router/debugging operation was performed in this follow-up.

1. **Unchanged revision integrity:** `syncCookbook` calls the production `verifyImage` (SHA-256 plus decoded dimensions) before considering any referenced image complete. Every sync rechecks bytes, including the first sync of a process and same-length changes after an earlier successful verification. A displayed cookbook image that fails pixel decoding is marked invalid; that marker prevents the fast path and forces a verified redownload through `cacheImage`. Failed repairs retain the existing file until a verified, fsynced staging file can atomically replace it.
2. **Incremental combined budget:** `cacheImage` and `save` use `OfflineAssets.stage`; synchronized admission reserves enough capacity for the whole staging file before connection/open/write. Interrupted staging bytes and both JSON indices are counted. Asset/size/hash/dimension or budget failures cannot replace an authoritative index or delete its existing asset as part of staging. Cleanup loads both keep sets under the same lock. Private per-instance budget/per-file defaults are reflected by the host tests only to scale the 604 MiB scenario; there is no user/API configuration or changed production limit.
3. **Collection transaction versus trim:** the independent read-only `TrimRaceProbe.java` demonstrates that per-asset locking allowed a second Activity to trim incoming deck files before the first saved its index. `poll` now calls production `syncDeck`, which holds `OfflineAssets.class` from asset caching through `state.json` save. `syncCookbook` holds the same lock through completeness verification, downloads and `cookbook.json` save. A trim cannot enter the download-to-commit gap for either collection. `destroyed` is volatile; reads, asset/collection loops and index admission check destruction/interruption. Trim checks cancellation before deletion so interrupted index reads cannot produce a destructive partial keep set. `onDestroy` still uses nonblocking `shutdownNow`; correctness does not depend on awaiting workers on the UI thread. Abort releases the lock and leaves the old authoritative indices/assets available for the next Activity's trim.

## Regression files and coverage

The previous nine regressions were written before the preceding production fixes. The harness invokes actual private `MainActivity.poll`, `syncCookbook`, `cacheDeck`, `cacheImage`, `save`, `verifyImage` and `trimCache` methods through reflection, with the actual `OfflineAssets` implementation. No copy of the sync/cache algorithm is mocked or reimplemented. The HTTP URL handler supplies byte streams without sockets; Android constructor/UI/handler/JSON shims are test-only. The bounds shim uses real JDK ImageIO PNG decoding, so this is host production-logic coverage rather than proof of Android BitmapFactory/device behavior.

| File | Purpose |
| --- | --- |
| `android/src/com/ian/frame/MainActivity.java` | Verified fast path, decode-failure marker, admission before downloads/index writes, atomic repair preservation, complete collection transactions and trim under a shared lock, cancellation checks |
| `android/src/com/ian/frame/OfflineAssets.java` | Combined disk accounting, synchronized stage/trim, image/index staging cleanup |
| `tests/java/com/ian/frame/MainActivityCacheTest.java` | Nine prior regressions plus four new transaction/trim and lifecycle-abort regressions |
| `tests/java/com/ian/frame/BuildConfig.java` | Synthetic test constants; no owner configuration read |
| `tests/java/android/app/Activity.java`, `tests/java/android/content/Context.java` | Host constructor/API shims; UI methods are not exercised |
| `tests/java/android/os/Handler.java` | Queued UI callback shim; retains worker/UI separation |
| `tests/java/android/graphics/Color.java`, `tests/java/android/graphics/BitmapFactory.java` | Constructor color conversion and real host PNG bounds decoding |
| `tests/java/org/json/JSONObject.java`, `tests/java/org/json/JSONArray.java` | Test-only JSON parsing/serialization |
| `tests/run_java_cache_tests.py` | Compile production against API 23 SDK, then host harness; run existing navigation/cache test plus new regressions |
| `COOKBOOK_IMPLEMENTATION_REPORT.md` | Corrected cache-bound claims and current commands/results |

The nine previously passing regressions cover:

- Unchanged-revision **nonempty truncation**, selective redownload, valid fast path, unchanged index and later mutation.
- Unchanged-revision **same-length pixel-data corruption**, selective redownload and later mutation.
- Hash-valid wrong dimensions cannot take the fast path.
- Decode-failure invalidation forces a redownload and clears after verified repair.
- Interrupted repair leaves the old file intact and removes partial staging.
- Two 19-image decks plus two 50-recipe cookbook generations at a 1:256 scale (4096 bytes per MiB), including observed live `.tmp` bytes, rejection before the 480 MiB equivalent, preservation of both authoritative indices and all their asset bytes, and successful retry after orphan cleanup.
- Preexisting interrupted `.tmp` bytes block admission before an image request; index staging also counts against the disk budget.
- Truncated downloads never publish an image or leave partial staging.
- Concurrent writers sharing a directory admit only one of two individually fitting downloads; admission/write is serialized.

Four added regressions use two actual `MainActivity` subclasses sharing one directory. Deck tests invoke real `poll` on its real worker; cookbook tests invoke real `syncCookbook`. The host subclass pauses the actual `save` directory lookup after all incoming assets have downloaded and before index publication. A second Activity invokes actual `trimCache` on another thread. Tests require it to block until commit, then check the published index, all incoming files and the other collection's assets. The same schedule also invokes actual `onDestroy` for each collection; interruption must abort, let trim finish, preserve both old indices and all their asset bytes, and prune incoming orphans. Transport/framework shims are unchanged; no transaction/cache implementation is duplicated. These four cases have been type checked but cannot be claimed as runtime passes in this sandbox.

## Current validation results and exact commands

JDK: `/opt/homebrew/Cellar/openjdk@17/17.0.20.1/libexec/openjdk.jdk/Contents/Home`. Python: `/Users/hermy/.hermes/household/meal-planning/venv/bin/python`. SDK jar: `/Users/hermy/.hermes/cache/scratch/framebot-sdk/platforms/android-23/android.jar`. No owner build config/key was read.

Parent reports that the preceding cache fixes passed **54 root Python tests + 4 protocol tests + all 9 executable Java cache regressions**, and that a **real API 23 unsigned APK build passed**. Those are completed parent validations, not outstanding SDK/test blockers. They precede this final transaction-race patch. Signing, device installation/visual checks and remote merge remain unperformed.

| Check | Actual result for the final transaction-race patch |
| --- | --- |
| Existing protocol tests | **4 passed**, 0.302 seconds |
| Production Android source type checking against API 23 | **Passed**, JDK 17/source 8; compiler stopped after FLOW analysis without generating class files |
| Production + host regression source type checking | **Passed**; same no-output FLOW analysis; expected source-8 bootstrap-classpath warning |
| Python runner syntax | **Passed** in memory, no bytecode/temp files |
| Executable Java regressions (now 13 cache cases + navigation/cache harness) | Attempt blocked at new scratch directory creation: `PermissionError: [Errno 1] Operation not permitted`. No classes/fixtures generated and no red/green runtime outcome claimed for this patch; parent rerun required |
| Root Python renderer/API/socket suite | Not rerun for this Android-only patch; parent previously passed **54 root tests**, separately from the **4 protocol tests** |
| Actual catalog/HTTP readback | Parent reports 50 actual recipes rendered and all 100 external catalog references verified; catalog/renderer were not opened or changed here |
| API 23 unsigned APK | Parent's preceding real build **passed**; rebuild required for this final patch |
| Signing/device installation/Original photos/remote merge | **Not performed** |
| `git diff --check` | **Passed** |

The attempted Java command (failed at scratch directory creation):

```sh
/Users/hermy/.hermes/household/meal-planning/venv/bin/python -B tests/run_java_cache_tests.py \
  --work-dir /Users/hermy/.hermes/cache/scratch/framebot-final-cache-race-tests \
  --jdk /opt/homebrew/Cellar/openjdk@17/17.0.20.1/libexec/openjdk.jdk/Contents/Home \
  --android-jar /Users/hermy/.hermes/cache/scratch/framebot-sdk/platforms/android-23/android.jar
```

The successful protocol command:

```sh
TMPDIR=/Users/hermy/.hermes/cache/scratch \
  /Users/hermy/.hermes/household/meal-planning/venv/bin/python -B -m unittest discover -s tools -p 'test_*.py'
```

The successful no-output production type-check command:

```sh
/opt/homebrew/Cellar/openjdk@17/17.0.20.1/libexec/openjdk.jdk/Contents/Home/bin/javac \
  -proc:none -XDshould-stop.ifNoError=FLOW -source 8 -target 8 \
  -classpath /Users/hermy/.hermes/cache/scratch/framebot-sdk/platforms/android-23/android.jar \
  android/src/com/ian/frame/*.java tests/java/com/ian/frame/BuildConfig.java
```

Host type checking used the same flags and jar, with all `.java` sources under `android/src` and `tests/java` supplied in one invocation; no class files were generated. Both checks emitted only the expected source-8 bootstrap-classpath warning.

Parent should rerun the exact Java command above in a writable scratch context and rebuild the unsigned API 23 APK after this final patch. The root suite's preceding pass remains recorded; use `TMPDIR` inside the scratch root for any new Python suite run. No alternate system-temp directory was used, and no sandbox escalation was requested. Existing deployment/build/access procedures remain in [docs/COOKBOOK_DEPLOYMENT.md](docs/COOKBOOK_DEPLOYMENT.md).
