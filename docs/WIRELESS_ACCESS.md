# Wireless debugging and recovery on this PF1007L

Normal content pushes require only the installed gateway/client. Debugging is needed for APK updates, screenshots, or Android diagnostics. After the verified final reboot, ADB port 5555 was closed and the frame continued to poll the gateway.

## Observed device state

- PF1007L / Allwinner A33 (`sun8i`), Android 6.0.1.
- Existing `/system/xbin/su` worked; root ADB became available after a runtime command through AiMOR.
- AiMOR package: `com.efercro.os.aimor`; updater: `com.yhk.qeota`.
- Current custom package: `com.ian.frame`, sole enabled HOME after both original packages were disabled.
- Firmware: `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113`.
- IP moved from .207 to .221 to .34; Wi-Fi MAC differs from the About page and changes. Read the current Wi-Fi details or router client list; do not rely on an old MAC.
- USB debugging never enumerated in the earlier attempts. Wi-Fi access was successful; no TF card was required.

## Re-enable temporary network ADB

This procedure uses the installed original software's vendor channel, as described in [the upstream AiMOR research](https://github.com/wesbos/photo-frame-dashboard/blob/main/docs/aimor-remote-root-shell.md) and [PF1007L network notes](https://github.com/wesbos/photo-frame-dashboard/blob/main/docs/pf1007l-20260410-network-adb.md). It was successfully used on this user's frame before switching to the custom launcher. It has not been repeated since the final reboot.

1. Long-press **FRAME** in the custom app and choose **Original photos**. This enables AiMOR/updater and starts AiMOR; it must be running to establish its vendor connection.
2. Confirm the frame's current private IP and this Mac's LAN address. The current gateway is `192.168.1.128:8765`; the debug listener uses port **7806**, not 8765.
3. Start the narrowly scoped helper, supplying the current frame IP:

   ```sh
   /usr/bin/python3 -B tools/frame_adb_listener.py --frame-ip CURRENT_FRAME_IP --bind YOUR_MAC_LAN_IP --seconds 300
   ```

   It rejects other source IPs, waits for AiMOR login command 110009, and sends one runtime command: `setprop service.adb.tcp.port 5555; stop adbd; start adbd`. It responds to empty 101 heartbeats and exits after transmission. It does not decode/log login payloads or modify firmware.
4. Temporarily make the frame resolve **`imsconnect.efercro.com`** to the Mac's LAN IP. The original session used a UniFi static A record with TTL 30. A router-wide override affects other clients resolving that hostname while it exists; keep it brief. Record any pre-existing DNS entry so it can be restored. Authenticate normally to the owner's router; credentials are not in this repo.
5. Reconnect the frame's Wi-Fi so it opens a new vendor session against the listener. The previous session used the router's client reconnect/kick command after confirming the current randomized MAC.
6. Watch for `runtime_adb_command_sent`, then independently verify using the tested Google platform-tools 35.0.2 binary:

   ```sh
   /private/tmp/frame-wireless/adb35/platform-tools/adb connect CURRENT_FRAME_IP:5555
   /private/tmp/frame-wireless/adb35/platform-tools/adb -s CURRENT_FRAME_IP:5555 shell id
   ```

   Sending the vendor command alone is not evidence that ADB worked. If refused, check AiMOR is actually running, current IP, DNS, router/client isolation, and Mac listener reachability.
7. Immediately remove the temporary DNS record or restore the exact previous entry. Confirm normal DNS resolution and stop the listener. In the completed session, the record list was empty afterward and public resolution was restored.
8. While root ADB is enabled, restrict inbound port 5555 to this Mac's actual address. The previous session inserted IPv4 rules with the specific Mac ACCEPT rule before a general REJECT, plus an IPv6 REJECT. Rules were runtime only. Inspect current rules before changing them; avoid duplicate or unrelated firewall changes.

The helper defaults to loopback and requires explicit private frame/bind addresses for real use. `--dry-run` creates a packet without network contact. Its protocol/peer tests run from the repository test commands.

## Install an updated APK and return to custom HOME

Keep the existing local signing key and read token before building. With independently verified ADB:

```sh
adb -s CURRENT_FRAME_IP:5555 install -r android/build/frame.apk
adb -s CURRENT_FRAME_IP:5555 shell am start -n com.ian.frame/.MainActivity
```

Use `su` or the verified root shell to disable `com.efercro.os.aimor` and `com.yhk.qeota` again so the custom app is the sole HOME. For the previously rooted ADB session these were `pm disable` operations; check current shell privileges before using them. Confirm the app works, Original photos still restores access, and package state is persisted before reboot. Opening Original photos re-enables the original packages, so switching HOME back is necessary after that test.

An existing-key `install -r` preserves app-private state/settings. A signature mismatch means the wrong key was used; copy the original key rather than uninstalling the working application.

## Restore original photos

Use the app's **Original photos** button, or, if ADB is active and root verified:

```sh
adb -s CURRENT_FRAME_IP:5555 shell pm enable com.efercro.os.aimor
adb -s CURRENT_FRAME_IP:5555 shell pm enable com.yhk.qeota
```

Launch AiMOR using the launch intent/package launcher, or reboot after verifying its enabled state. Uninstalling `com.ian.frame` is optional and deletes its cached content/settings; only do so when the user wants a full return to stock app behavior.

## Backups and clean final state

`backups/boot.img`, `backups/recovery.img`, and `manifest.json` are retained only in the original local checkout. Each 32 MiB partition was independently read twice and hashes matched. These are limited backups. They do not include system/userdata and were never flashed. Use model-specific recovery research and explicit owner intent before any future flashing.

At handoff: temporary DNS override removed, one-shot listener stopped, original AiMOR/updater installed but disabled, custom HOME confirmed after reboot, gateway active, frame polling, ADB closed. This is the working everyday state.
