# Token-free LAN push access

Enabled at Ian's explicit request on October 12, 2026: any device on `192.168.1.0/24`, and any local Mac profile through loopback, can push cards without a token. The gateway is `http://192.168.1.128:8765`. Other Mac profiles use a shared client, without reading Ian's private Library or obtaining his credentials.

## From shell-e or any profile on this Mac

```sh
/usr/bin/python3 -B /Users/Shared/HermesFrameClient/framectl.py status
/usr/bin/python3 -B /Users/Shared/HermesFrameClient/framectl.py text "From Hermes" "Your update here" --id hermes
/usr/bin/python3 -B /Users/Shared/HermesFrameClient/framectl.py image /absolute/path/photo.jpg --id photo
/usr/bin/python3 -B /Users/Shared/HermesFrameClient/framectl.py json -
```

The JSON command takes a payload through stdin. Use argv arrays rather than interpolating generated text into a shell command. Read local image files as the invoking profile; this client does not grant access to another profile's personal files.

## From any LAN device

```sh
curl --noproxy '*' --fail-with-body http://192.168.1.128:8765/push \
  -H 'Content-Type: application/json' \
  --data '{"card":{"id":"hermes","type":"text","title":"Hello","body":"Sent over Wi-Fi"},"focus":true}'
curl --noproxy '*' http://192.168.1.128:8765/status
```

A cloned client can also connect without configuration:

```sh
python3 -B framectl.py --url http://192.168.1.128:8765 text "Hello" "From another device"
```

Images use the existing image CLI or PNG/JPEG/WebP data URI in the `image` field. Reusing a card ID replaces that card; new IDs append cards. Use `focus:false` in JSON, or `--no-focus`, for background updates. The default maximum remains 20 cards. No credentials or pairing are required for these pushes.

## Exact access

- `POST /push` and `GET /status` allow token-free access from the configured subnet and loopback.
- Any admitted device can add or overwrite a card, including existing photo/text cards; there is no per-device identity or content ownership in this mode.
- `DELETE /cards/ID` retains owner-token authentication. The default clock remains a clock, and default clock/Hermes cards cannot be deleted.
- Frame reads of `/state` and `/media` retain their existing read token.
- The source IP comes from the socket, not `X-Forwarded-For` or other headers.
- No router port forwarding or firewall changes were made. Other routed subnets are not automatically included. Add their CIDRs only when the user wants those networks admitted.
- The owner-run gateway and private data remain under Ian's profile. Ian's LaunchAgent must be running; logging Ian out stops it. Locking the session or switching profiles while Ian stays logged in works.

Configuration in the private live `data/config.json`:

```json
{
  "public_push": true,
  "public_push_networks": ["127.0.0.0/8", "192.168.1.0/24"]
}
```

These are additional fields; keep the existing `port`, `frame_url`, `read_token`, and `push_token`. To revoke open LAN push access, set `public_push:false` and restart `com.ian.hermes-frame`. No token rotation or APK rebuild is needed. If the subnet changes, update the CIDR and restart the service.

The staged `/Users/Shared/framebot-shell-e-setup/install_frame_client.py` is not needed and was not executed. Do not run it or copy the owner's tokens merely to enable this shared client.
