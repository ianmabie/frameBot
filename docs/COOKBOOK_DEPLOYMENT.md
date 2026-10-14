# Cookbook review and owner-run deployment

## Current gate status — October 14, 2026

Final independent review passed. Parent executed the final 54 root tests, 4 protocol tests, all 13 production-cache regressions and navigation harness successfully, and rebuilt the API 23 unsigned review APK. Exactly 50 real recipes rendered and passed local HTTP import/readback, with all 100 asset references verified and weekly deck unchanged. Historical rerun/sandbox notes below describe earlier sessions, not current blockers. User explicitly authorized remote merge, installation and necessary temporary DNS/debugging changes with immediate restoration. Physical deployment still requires the original owner signing key and authenticated router access; user is resolving that handoff. No live installation/DNS change has occurred. Never install the synthetic-config unsigned review APK.

This checkout contains source changes only. No live gateway files, deck, recipes, app, router or debugging configuration were changed. Parent reported frame `192.168.1.35`, active deck revision 33 on October 14; this session could not independently query it. Do not use stale `.34`.

## Review prerequisites

Parent reviews source, report, test results and the later caller-supplied catalog/images before commit/push or live deployment. Local `.git` is read-only under this session's permissions: branch creation was refused. Parent must run `git switch -c cookbook-tab` from the current uncommitted checkout in an authorized shell. No commit/push was attempted. Cookbook feature permission does not authorize accessing Ian's private key/config from shell-e or re-enabling debugging. Owner confirms the required deployment/access steps currently before they are executed.

The asynchronous content task supplies `/Users/hermy/.hermes/household/meal-planning/cookbook-catalog/catalog.json` and photos. This implementation does not poll that path. Validate/render after delivery using README's cookbook command into a new directory outside Git. Review all 50 detail images and thumbnails, copyright credits and representative labels. Overflow must be corrected in the catalog and rerendered; do not remove ingredients/steps or shrink type. Keep the weekly menu approval workflow separate.

## Test on an unrestricted development shell

Parent's preceding validation passed **54 root Python tests, 4 protocol tests and all 9 executable Java cache regressions**, plus a **real API 23 unsigned APK build**. Signing, device installation and remote merge have not occurred. The final transaction/trim fix adds four real-production regressions (13 cache cases total); source and harness type checking against API 23 passed, and protocol tests reran with 4 passes. Its executable runner was blocked only by creation of a new scratch directory in this sandbox. Parent must rerun those Java cases and rebuild the unsigned APK for this patch before deployment review.

From the reviewed checkout in a shell allowed to write the scratch root, with rendering dependencies and the supplied JDK/SDK:

```sh
PYTHON=/absolute/path/to/python-with-Pillow-reportlab-PyMuPDF
SCRATCH=/Users/hermy/.hermes/cache/scratch/framebot-final-cache-race-tests
mkdir -p "$SCRATCH"
export TMPDIR="$SCRATCH"
"$PYTHON" -B -m unittest discover -p 'test_*.py'
"$PYTHON" -B -m unittest discover -s tools -p 'test_*.py'
"$PYTHON" -B tests/run_java_cache_tests.py \
  --work-dir "$SCRATCH" \
  --jdk /opt/homebrew/Cellar/openjdk@17/17.0.20.1/libexec/openjdk.jdk/Contents/Home \
  --android-jar /Users/hermy/.hermes/cache/scratch/framebot-sdk/platforms/android-23/android.jar
```

The Java runner compiles real production Android sources against API 23, then runs them with host transport/framework shims. The four new cases pause real deck/cookbook sync before index save while a second Activity sharing the directory attempts real trim, and verify both commit and `onDestroy`/abort paths. Host bounds decoding uses ImageIO; Android device decoding/visual behavior still requires owner verification. See [the report](../COOKBOOK_IMPLEMENTATION_REPORT.md) for exact current versus parent results.

## Build and sign, as Ian

After parent review and current authorization, Ian opens an owner shell on the mini and uses the reviewed source checkout. These commands use the existing config/key directly without generating/copying credentials. The original key stays in place. Fill `REVIEWED_CHECKOUT` with the actual reviewed source directory; do not use an old source snapshot accidentally.

```sh
REVIEWED_CHECKOUT=/Users/ian/Documents/frameBot-cookbook-reviewed
ORIGINAL_PROJECT=/Users/ian/Documents/Codex/2026-10-12/i-need-help-with-a-new/frame-project
cd "$REVIEWED_CHECKOUT"
export FRAME_SDK_ROOT=/private/tmp/frame-wireless/build-tools
# If the temporary SDK is gone, select an owner-installed Android SDK and JDK 17.
/usr/bin/python3 -B build.py \
  --config "$HOME/Library/Application Support/HermesFrame/data/config.json" \
  --keystore "$ORIGINAL_PROJECT/android/build/frame.keystore"
```

The default temporary SDK discovers its bundled JDK. For a durable SDK, also set `JAVA_HOME` to its JDK 17. Build output is `android/build/frame.apk`; `apksigner verify --verbose --print-certs` runs automatically. Compare its signer certificate SHA-256 with the previously verified original installed-build APK using the same SDK's `apksigner verify --print-certs`. If no trustworthy baseline/key is available, stop. Do not generate another key or uninstall the working app. Never commit the config, generated BuildConfig, keystore or APK containing the read token.

## Owner gateway update

Only Ian runs these commands, after the review and current deployment authorization. Existing live data is preserved by the deploy script; do not initialize tokens or copy checkout state over live state.

```sh
cd "$REVIEWED_CHECKOUT"
/usr/bin/python3 -B deploy_gateway.py
/usr/bin/python3 -B /Users/Shared/HermesFrameClient/framectl.py status
/usr/bin/python3 -B "$HOME/Library/Application Support/HermesFrame/framectl.py" cookbook
```

The deploy script copies `gateway.py`, `framectl.py`, `cookbook.py` and `cookbook_import.py`; it installs all client dependencies in `/Users/Shared/HermesFrameClient/` too. It does not replace an existing live data directory. Verify the deck revision and cards match the baseline before any cookbook import. Do not deploy this service as shell-e or alter its ownership.

## Owner APK update and visual/offline verification

ADB was closed after the earlier reboot. Read [WIRELESS_ACCESS.md](WIRELESS_ACCESS.md). Its vendor-channel/router/debugging procedure requires the owner's current confirmation; feature authorization alone does not grant that step. Independently verify ADB privileges/current frame IP after the owner performs the approved procedure. Then, with the correctly signed APK:

```sh
/private/tmp/frame-wireless/adb35/platform-tools/adb -s CURRENT_FRAME_IP:5555 install -r android/build/frame.apk
/private/tmp/frame-wireless/adb35/platform-tools/adb -s CURRENT_FRAME_IP:5555 shell am start -n com.ian.frame/.MainActivity
```

No uninstall, partition flashing or new signing key. Follow the documented original-package/HOME restoration and temporary-debugging cleanup. Retain the Original photos escape; verify it under owner supervision and restore custom HOME afterward as documented.

After content review and authorization, dry-run then apply the rendered `manifest.json` using the updated client (README). Check `/status` and owner-authenticated `/cookbook`; confirm cookbook revision, 50 entries and original deck revision. On the frame verify Photos contains the prior photos/clock, This Week contains only existing accepted weekly IDs, and Cookbook displays seven pages (last page two entries). Check filters, thumbnail readability, recipe choice, all ingredients/steps, credit/representative label, detail swipes and Library return. Simulate gateway loss by stopping only the owner gateway service temporarily; verify restart and all cached cookbook pages/details while offline, then restore the service. Do not change Wi-Fi/router settings for this test. Verify a fresh update resumes; report accepted, cached and visually verified separately.

Source push is authorized only after parent review. Live deployment remains pending the current user authorization and required owner steps. No live publication occurs from the tests or render command.
