# B15 installation and target verification

## What this file authorizes and does not claim

This is the exact-source maintenance upgrade for the already-installed B14
SHT31/GPIO23 room appliance. It does not require rewiring, manually toggling GPIO,
or replacing the working environment controller. B15 is a host-tested repair
checkpoint; real wake/command/audio, no-login reboot and soak acceptance remain
unverified. No remote push or merge to main accompanied this download.

The full repair record is [REPAIR_RECORD.md](REPAIR_RECORD.md). The delivery ZIP
contains the source `.tar.bz2`, checksum file, delivery receipt, and a separate
copy of the final report. The source tar contains a complete `gonkenlabagent/`
Git checkout with the B15 branch and checkpoint tag, not just a patch.

## 1. Before installing

Keep the microphone and speaker connected. The latest supplied support snapshot
reported no usable input and auto_null.monitor, despite healthy environment
control. This might have been temporary, but it must not be treated as a working
microphone. Do not rewire the relay or SHT31.

Copy the source tar and its `GonKen_B15_SHA256SUMS.txt` from the download to the
Raspberry Pi home directory. These commands assume the files are there. Check
that the checksum passes, extract into a *new* directory, and leave the old
checkout untouched:

```bash
cd "$HOME" &&
sha256sum -c GonKen_B15_SHA256SUMS.txt &&
B15_DIR="$(mktemp -d "$HOME/gonken-b15-XXXXXX")" &&
tar -xjf "$HOME/gonkenlabagent-attempt03-b15-voice-repair.tar.bz2" -C "$B15_DIR" &&
cd "$B15_DIR/gonkenlabagent" &&
git status --short &&
git log -1 --oneline &&
git tag --points-at HEAD
```

`git status --short` must print nothing. The tag must include
`checkpoint/attempt03-b15-voice-repair`. Compare the full commit and checksum
against the included delivery receipt. No archive or receipt is a hardware PASS.

Read-only checks before upgrade:

```bash
arecord -l
gonken-agent env health --json
gonken-agent env policy show
```

`arecord -l` should list the USB capture device when it is attached; a missing
capture device needs a physical connection/enumeration correction. Do not run a
second recorder while GonKen already owns the microphone. A default monitor source
alone does not count as a microphone.

## 2. Install these exact downloaded bytes, preserving your policy

From the extracted `gonkenlabagent` directory:

```bash
sudo -v
./bootstrap.sh --local-checkpoint --environment-profile full-real --environment-mode preserve --appliance-preset none
```

The `--local-checkpoint` flag matters: without it, the bootstrap normally resolves
remote main, which may still be B14. The explicit environment/preset options avoid
resetting your selected model, thresholds and operating mode to the factory
responsive-room defaults. The existing installer manages immutable releases and
service restart; do not copy individual Python files into `/usr/local/lib`.

The new native wake prerequisites are Debian `libpocketsphinx3` and
`pocketsphinx-en-us` (with their distro dependencies). The existing apt phase
installs them. Normal operation remains offline, but dependency installation may
need access to configured Debian repositories. Model weights are not in the
source archive. Existing Ollama/Whisper/Piper provisioning remains unchanged.

If installation fails, use the one combined failure-support archive printed by
the installer. Do not run another support command after an install failure unless
the failure report says collection itself was unavailable. Do not claim success
from an active systemd process without the installer's current postconditions.

## 3. Confirm identity and configured backend

```bash
readlink -f /usr/local/lib/gonken-agent/current
gonken-agent wake status --json
gonken-agent components --json
gonken-agent env health --json
gonken-agent env policy show
systemctl --no-pager --full status gonken-agent.service gonken-environment.service ollama.service
```

The active release path must end with the B15 commit in the delivery receipt.
Wake status should show `capture.mode=streaming-kws-vad`,
`wake_and_command_share_capture=true`, and
`capture_continues_during_transcription=false`. The last value is intentional:
one complete utterance is captured, then the recorder closes before speech
playback or transcription. Wake status is configuration information, not proof of
live native dependency usability or physical recognition.

The environment should retain `sht31`, `libgpiod`, GPIO23 and your previous policy.
`physical_evidence=false` remains an evidence qualifier, not a simulation switch.

## 4. Voice checks, in this order

First test read-only queries. Say `GonKen` alone, wait for `Yes?`, then ask `What is
the temperature?`. Repeat with `What is the humidity?` and `What time is it?`.
Next say each as one sentence: `GonKen, what is the temperature?` and `GonKen,
explain photosynthesis.` The inline request should not trigger another command
recording or an intervening Yes?.

Observe automatic fan operation as room temperature naturally crosses your
existing thresholds. Normal transitions should say `Fan actuator started.` and
`Fan actuator stopped.` Do not alter thresholds merely to force quick relay
cycling. The ordinary automatic safety/dwell policy remains active.

Only after read-only commands work, test any desired manual fan command while
supervising the fan. A manual fan command changes the existing mode to manual;
restore automatic control afterward:

```bash
gonken-agent env mode automatic
```

Speak complete timed requests rather than separating `fan on` and `in two
minutes` by a long silence. Native streaming utterances stop after the configured
silence (900 ms by default), and continuous utterances reaching 12 seconds are
discarded rather than executed as incomplete commands.

## 5. Measure, rather than assume, responsiveness

```bash
sudo journalctl -u gonken-agent.service -b --no-pager -n 200 | grep -E 'WAKE_STREAM_METRICS|VOICE_CAPTURE_METRICS|WAKE_DETECTED|VOICE_TURN_COMPLETE|AUDIO_|WAKE_NATIVE_'
```

Look for capture completion, one command transcription and VOICE_TURN_COMPLETE,
not a cycle of AUDIO_CAPTURE_WAV_INVALID and repeated ready announcements.
Native keyword detection avoids Whisper for successfully detected wake-only
utterances. When the native detector misses a pronunciation, the complete-utterance
Whisper fallback can still take several seconds. General answers and command
transcription have their own latency; lowering the Ollama model size does not
remove those stages.

Record a few observations of wake-only and inline queries, noting whether the
stream metric says `native_keyword=True` or `fallback=True`. The supplied host
synthetic timings are not Pi measurements. Do not tune the keyword threshold
merely to maximize hits: the more permissive synthetic trial caused false wakes.

## 6. Reboot and recovery acceptance

After successful basic voice checks, reboot when no timed/important operation is
in progress. Check that services and automatic policy return without a console
login, then repeat a wake-only and inline temperature query. Physically observe
that the speaker and microphone work; a readiness file alone is insufficient.

The latest prior boot had no microphone. If that recurs, inspect the USB connection
and capture enumeration, and let the voice service retry after device recovery.
The environment controller should continue independently of audio/model faults.

For a post-install voice problem, collect the ordinary single support archive:

```bash
/usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

The command prints its actual output path. B15 adds bounded voice timing records
to `service_events.json`; no raw conversation audio or transcripts are needed.
Keep the source tar and receipt so any later report can be bound to the exact
installed commit.

## Remaining / next action

Completed host implementation: raw PCM finalization, inline/standalone voice
control flow, short actuator announcements, bounded streaming capture, native
wake adapter with utterance fallback, recovery wording and support metrics.

Remaining target evidence: native recall/false wakes, cold/warm/distance/noise
latency, actual Whisper/Piper command-to-answer behavior, USB availability after
reboot, no-login startup, and continued automatic thermostat operation. The wider
Attempt03 display/cleanup programme is not closed by this repair.

Continuation instruction: Continue from the recorded checkpoint and execute the
next dependency-ready batch. Start by comparing the B15 target support archive
against this exact source; do not reopen unrelated architecture or replace
working sensor/relay control based on historical failures.
