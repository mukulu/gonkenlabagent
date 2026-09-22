# B15 voice-runtime repair: source, diagnosis, implementation and limits

## Verdict

B15 is a host-tested repair checkpoint descended from the exact B14 installed
source. It is not a claim of an error-free system, physical Raspberry Pi audio
acceptance, or completion of the larger Attempt03 programme. The final selected corpus contains 1,011 unit and 97 integration/lifecycle tests
(1,108 distinct tests, no skips or missing cases). See
`verification/VERIFICATION.json` for final test accounting and the adjacent
package receipt for exact exported-byte qualification.

## Source recovery and authority

The supplied archive `gonkenlabagent-attempt03-b14-power-probe-fix.tar(1).bz2`
was actually readable in this continuation's runtime. Its SHA-256 is
`52713e418f7762ab655fc102314cadccfb7017337c3bd18645c2bf0778e2d6b6`, and its HEAD is
`648f5b151d4c753cf1660243afacd010d73d05b7`. The connected GitHub main branch was
independently read at that same commit; no B15 branch was found. Earlier claims
that source could not be recovered no longer apply. No prior B15 modifications
were recovered. The interrupted attempt was marked INTERRUPTED; implementation
was resumed on `dev-unstable/attempt03-b15-voice-repair` without rewriting main.
This is checksum verification, not a claim of a cryptographic signature.

Input identities are in `verification/diagnostic_source_hashes.json`. The older
Checkpoint-42/45 documents remain lineage, not the B14 runtime source authority.

## Confirmed observations, diagnosis and repaired layer

### Wake backlog

FACT: the uploaded September 22 journal reports two-second wake windows,
recognition taking approximately 3.1-3.4 seconds, and stale-window drops up to
150. B14 `WakeCapturePipeline` calls Whisper for every window, including silence.
INFERENCE: recognition slower than incoming audio causes the observed backlog;
shrinking Ollama cannot fix that preceding stage. The small warm Ollama health
transactions in the log do not measure a complete voice conversation.

REPAIR: one recorder produces S16_LE/16 kHz/mono frames; a native phonetic keyword
search receives 80 ms frames. A speech endpoint segmenter retains a 400 ms RAM
pre-roll and up to 12 seconds of speech, including both name and command. It ends
after the configured silence, 900 ms by default. Silence never enters Whisper.
One completed utterance is handed to the consumer, and the recorder is closed
before TTS/transcription. There is no growing Whisper-window queue. A native miss
can use one full-utterance Whisper check; this fallback retains recall but can
still take the installed Whisper model's full transcription time.

### Invalid command WAV

FACT: after WAKE_DETECTED, target logs report AUDIO_CAPTURE_WAV_INVALID. Source
inspection shows interrupted ALSA WAV recording was entrusted to the recorder's
container finalization. A target-shaped regression reproduces the rejection of a
WAV whose header still promises eight seconds after only one second was written.
LIMIT: the original failed WAV was not retained, so this does not prove that its
header, rather than another low-level capture fault, was the exact target cause.

REPAIR: ALSA and Pulse now share raw-PCM capture with GonKen-owned WAV finalization
after the child is reaped. Empty, odd-byte, oversized, timed-out and nonzero-error
captures are rejected. Cancellation and temporary-file cleanup remain bounded.
Subprocess pipe tests exercise fragmentation, stderr backpressure, EOF, stalls,
cancellation and a child ignoring SIGINT. Capture errors retain explicit codes.

### Ready-announcement loop and lost inline words

FACT: capture errors returned the runtime to startup probing and a repeated
ready announcement. B14 also stopped its wake recorder before a separate command
capture, which could discard a command already spoken with the wake name.

REPAIR: successful startup speech happens once per service instance; recovery
still reruns functional probes without repeating that speech. A complete inline
request goes directly to normal typed routing, without Yes? or another recording.
A native wake-only event says the cached Yes? and captures the following request.
A native attention hit alone does not authorize a wakeless inline command.
Numeric signs/decimals survive wake-prefix removal. Truncated maximum-length
utterances are discarded, not executed as incomplete timed actions.

### Actuator announcements

Normal autonomous transitions say exactly `Fan actuator started.` and
`Fan actuator stopped.` Simulation keeps its short simulation prefix. Sensor
failure says safe-off was requested; actuator errors leave state unconfirmed.
No failure is reworded as successful actuation. Internal evidence and error
reporting remain separate from ordinary short spoken confirmations.

### Later microphone absence

FACT: the later supplied support archive, on a different boot, reports
AUDIO_INPUT_NOT_FOUND_USB_OR_BLUETOOTH, default source auto_null.monitor, and no
usable microphone, while the environment controller remains READY and automatic.
The cause of device disappearance is not established. Software cannot capture a
physically unavailable microphone. B15 retains USB/PipeWire route fallback and
recovery, but microphone enumeration/no-login hotplug must be retested on the Pi.

## Why not simply copy Jansky's openWakeWord model?

The original project uses its custom Hey Jansky ONNX keyword model followed by
Whisper command recognition. That model is not a GonKen model. No trained GonKen
model was supplied. B15 therefore uses Debian's native PocketSphinx phonetic
keyword search, explicit GonKen pronunciation alternatives, and full-utterance
Whisper fallback. This is not represented as an openWakeWord implementation.

The native ABI is deliberately limited to libpocketsphinx.so.3 / libsphinxbase.so.3,
which Debian Trixie provides, with the distro pocketsphinx-en-us acoustic model.
The installer installs these through the existing apt prerequisite path before
release construction. No new pip dependency, global Python import-path bridge,
cloud request, downloaded custom keyword model, or post-seal payload mutation is
introduced. Ordinary operation remains offline. Model weights are not bundled
in this source checkpoint. Model/library availability is checked before voice
readiness. Unsupported native phrases fail explicitly; the old Whisper backend
remains selectable for a deliberately configured non-GonKen phrase.

## Synthetic characterization: not a recognition-quality certificate

At the selected conservative native threshold 1e-20, a 36-case eSpeak/SoX corpus
(two synthetic voices) produced 6 native hits among 12 intended wakes and no native
hits among 24 negative phrases. This exposed misses, not a complete acoustic PASS.
Native processing consumed about 2.35 seconds for 110.32 seconds of synthetic audio
on this x86_64 host, with approximately 2.86 ms p95 per 80 ms frame. These numbers
are neither Pi latency nor human recall estimates. See the exact JSON and rerun
script `scripts/characterize_native_wake.py`.

A 1e-30 trial produced 8/12 positives and 0/24 negatives; 1e-40 produced 10/12
positives but 4/24 negative hits, including fan announcements. The more permissive
trial was rejected. The conservative default and utterance-level fallback were
kept instead of presenting a higher synthetic hit count as a solved wake model.
Cold/accent/distance/noise performance, Whisper transcription accuracy and true
microphone-to-speaker latency remain physical target acceptance items.

## Ownership and non-regression boundaries

Environment sensor/control/relay source is unchanged from B14. GPIO23 has the
same single environment-daemon owner. Voice continues to use typed intents/IPC;
no model-generated shell or raw GPIO action is introduced. Existing automatic
policy, dwell, timers, power confirmation, optional-Bluetooth behavior, immutable
releases, current-state integrity, rollback and systemd supervision are retained.
The maintenance install command explicitly preserves the current policy/model
instead of reapplying the factory responsive-room preset.

## Observability and privacy

WAKE_STREAM_METRICS records native hit/fallback, utterance duration, maximum
native-frame decode time and transcription time. VOICE_CAPTURE_METRICS separates
follow-up capture and transcription. Ordinary support collection includes a
bounded list of numeric/boolean timing fields in service_events.json. It does
not copy transcripts, raw audio, prompts, model responses or arbitrary journals.
`wake status --json` describes the actual configured backend and explicitly does
not claim to verify live dependencies or physical recognition.

## Why earlier checks missed this

Prior tests verified window queuing and isolated captures, but did not connect
a slower-than-real-time wake consumer, an interrupted ALSA WAV, the subsequent
command handoff, and repeated readiness speech. B15 tests join these boundaries:
whole utterance retention, no second capture for inline requests, native misses,
false attention without wake-bearing commands, bounded child cleanup, raw-WAV
finalization, recovery speech and content-free support timings.

## Final false-green review correction

A final source review found that one intended cleanup insertion had not actually
matched the current wake-loop layout: a producer-stop failure after handing its
WAV to the consumer could leave that temporary file behind. The new regression
`test_stop_failure_cleans_consumer_owned_audio_without_routing` failed before the
fix. The wake-loop finally block now owns cleanup of the handed-off WAV even when
stopping fails. A 53-test wake/capture regression then passed. The original failed
reproduction log is preserved; it is not counted as a passing product test.

## Remaining gates and continuation

Host implementation and package checks are recorded independently from target
acceptance. The strict whole-program release promotion gate is not weakened and
may correctly remain NOT_READY for unfinished historical programme slots.
Development archive qualification does not promote this to a stable-final release.
The next action is the exact B15 target installation and the voice matrix in
`INSTALL_AND_VERIFY.md`, after confirming the microphone is physically connected.
Continue from the recorded checkpoint and execute the next dependency-ready batch.

## External primary-source comparison register

Inspected on 2026-09-22: upstream `mayukh4/pibot_local_agent` README blob
`9458f9885f3972f6cd1c33d195d3a57c22ff421d` and
`senses/wake_word_detector.py` blob `e491fecbb8b268193df5554e19c24abefafe7844`.
The code uses 3,840 samples at 48 kHz (80 ms), adaptive gain, decimation and
openWakeWord; it closes the stream before invoking the command callback. Its
fallback when a custom model is missing is a bundled Hey Jarvis model, not a
GonKen model. B15 preserves the separation of lightweight wake and full STT, but
uses the explicitly described different phonetic backend and adds continuous
same-utterance retention rather than claiming to copy that trained keyword model.

Primary documentation consulted:

```text
https://github.com/mayukh4/pibot_local_agent
https://pocketsphinx.readthedocs.io/en/latest/pocketsphinx.html
https://packages.debian.org/trixie/libpocketsphinx3
https://packages.debian.org/trixie/pocketsphinx-en-us
```

The old Trixie native ABI is the implementation dependency, not the newer Python
PocketSphinx package documented by pip examples. Offline host characterization
used the installed Debian library/model; no external source weights are copied
into this package.
