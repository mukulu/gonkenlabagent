# Headless Bluetooth audio

Bluetooth is an optional GonKenLab transport. USB audio remains a valid fallback
and the repository never hard-codes a speaker/headset name or MAC address.

## Installation

Preferred deterministic form:

```bash
./bootstrap.sh --bluetooth-audio --bluetooth-device AA:BB:CC:DD:EE:FF
```

A unique name substring may be supplied instead, or omit the selector for guided
discovery.

## Prerequisite reconciliation

When Bluetooth is requested the installer verifies and, where safely possible,
repairs the required stack in this order:

```text
BlueZ packages/service
  -> Bluetooth controller exists
  -> reject hard rfkill block
  -> unblock software rfkill
  -> power controller on
  -> verify controller active/unblocked/powered
  -> dedicated no-login PipeWire/WirePlumber user session
  -> pairing/routing
```

This is important on fresh Raspberry Pi images where the controller can exist
while the radio is still software-blocked or powered off.

Unlike Wi-Fi, Bluetooth does not require the installer to guess a regulatory
WLAN country.

## Device-selection policy

When `--bluetooth-device` is supplied:

1. an exact MAC is authoritative;
2. a known BlueZ device with that MAC is reused if suitable;
3. otherwise a bounded scan waits specifically for it;
4. a non-MAC selector is a case-insensitive name substring and must identify one
   audio-capable device;
5. without a selector, discovery must produce one unambiguous candidate.

The installer never silently selects an arbitrary nearby headset.

## Pairing lifecycle

For a new device, put it into pairing mode when bootstrap prints its pairing
action. Successful setup performs:

```text
identify -> pair -> trust -> connect -> resolve services
         -> PipeWire route -> managed device record -> autoconnect service
```

The managed record is:

```text
/etc/gonken-agent/bluetooth-device.record
```

It records the selected public device identity and coarse audio capability, not
audio content or pairing secrets.

## Headless audio ownership

Bluetooth system pairing belongs to BlueZ. Audio runs in a dedicated lingering
systemd user manager for the `gonken-agent` service account. The session is
created without desktop/SSH login and uses PipeWire/WirePlumber.

The package-level user units are already globally enabled on Raspberry Pi OS;
GonKen starts/verifies them rather than attempting to create per-user enablement
symlinks beneath the root-managed service home.

## Automatic reconnect

`gonken-bluetooth-autoconnect.service` is enabled at boot after Bluetooth. It
reconciles controller readiness, then attempts connection only to the recorded
trusted device. If the device is switched off, the helper retries at a bounded
interval; the main voice runtime also remains supervised and waits for an audio
path rather than forcing model reinstallation.

When the device becomes available the helper reconnects it and restores the
PipeWire default route. The voice service can then reach readiness/wake standby.

## Output vs headset microphone

A Bluetooth device can expose several profiles:

- A2DP: high-quality playback;
- HFP/HSP: bidirectional headset audio with lower playback quality.

For a headset-capable device, the managed setup first waits for both Bluetooth
output and input nodes. If the device initially exposes only A2DP output, it
selects an available headset/HFP profile with a capture source (preferring mSBC
when advertised), then sets the resulting Bluetooth sink/source as the dedicated
service user's defaults. This makes the fully wireless microphone + speaker path
explicit rather than relying only on opportunistic profile autoswitch.

The current managed Bluetooth mode treats the selected Bluetooth headset as the
default input/output pair. A mixed USB-microphone + Bluetooth-output topology is
architecturally possible, but it is not silently selected by FIX5. Use explicit
site/manual routing for such a deployment until independent managed input/output
selection is promoted into a later configuration contract.

## Manual inspection

```bash
rfkill list bluetooth
systemctl status bluetooth --no-pager
bluetoothctl show
bluetoothctl devices Paired
```

Managed extension status:

```bash
systemctl status gonken-bluetooth-autoconnect.service --no-pager -l
sudo /usr/local/bin/gonken-bluetooth status \
  --record /etc/gonken-agent/bluetooth-device.record \
  --audio-user gonken-agent
```

For service-user PipeWire details:

```bash
UID_GA="$(id -u gonken-agent)"
sudo runuser -u gonken-agent -- env \
  HOME=/var/lib/gonken-agent \
  XDG_RUNTIME_DIR="/run/user/$UID_GA" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$UID_GA/bus" \
  wpctl status
```

See [OPERATIONS.md](OPERATIONS.md) for logs and manual voice-runtime commands.
