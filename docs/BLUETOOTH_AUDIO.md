# Headless Bluetooth audio extension

Bluetooth is optional. The GonKenLab Agent core must remain installable and
recoverable with USB audio alone.

## Selection policy

The repository never hard-codes a headset/speaker name or MAC.

Priority when `--bluetooth-device` is supplied:

1. an exact MAC is treated as the authoritative identity;
2. if BlueZ already knows that MAC and it advertises audio capability, setup
   reuses it without requiring rediscovery;
3. otherwise a bounded scan waits specifically for that MAC;
4. a non-MAC selector is a case-insensitive name substring and must match one
   audio device only;
5. without a selector, exactly one unpaired audio-capable device must be visible.

Ambiguity fails closed instead of pairing a random nearby device.

## Headless ownership

BlueZ pairing/trust is system state. PipeWire/WirePlumber runs for the dedicated
`gonken-agent` account using systemd user lingering, so the audio graph exists
without an SSH/desktop login. A small root system service attempts connection to
only the recorded trusted Bluetooth MAC and asks the dedicated audio session to
restore its default route.

## Pairing lifecycle

During first setup bootstrap prints an `ACTION` message. Put the selected audio
device in pairing mode if it is not already known by BlueZ. Successful setup:

```text
controller -> stack ready -> identify -> pair -> trust -> connect
           -> PipeWire output route -> private device record -> autoconnect
```

The managed record is:

```text
/etc/gonken-agent/bluetooth-device.record
```

It contains the selected MAC/name and coarse audio capability flags, not audio
content or pairing secrets.

## Reboot/reconnect behavior

`gonken-bluetooth-autoconnect.service` starts after `bluetooth.service`. If the
trusted device is off, the helper remains alive with bounded exponential retry.
When the device becomes available it reconnects it and refreshes PipeWire's
default Bluetooth route. Failure does not stop `gonken-agent.service` or remove
USB audio.

## Bluetooth headset microphone

A device may advertise Handsfree/HFP and still expose its microphone only after
WirePlumber changes profile. High-quality A2DP output and bidirectional HFP audio
have different quality/latency properties. The extension records whether a
Bluetooth input node is currently visible but does not pretend that every
headset's microphone behavior is identical.

A stable mixed topology can therefore remain useful:

```text
USB microphone -> STT
Bluetooth A2DP output <- TTS
```

Future audio policy should select input/output independently rather than assume
one physical device must provide both.
