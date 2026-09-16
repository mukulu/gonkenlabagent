# V09 Checkpoint 33 Report — Runtime Stability and Optional Audio Convergence

## Purpose

Checkpoint 33 responds to the exact checkpoint-32 Raspberry Pi sequence: the current release built and activated successfully, progressed through hardware-binding/I2C/model/speech/application-service gates, then stopped because the preferred Bluetooth headset was busy; subsequent curl and local same-commit runs failed much earlier with `RELEASE_ACTIVE_INVALID`. The same support bundle also recorded deterministic AIRHUG USB input/output and repeated wake-LED GPIO line ambiguity.

## What the two release errors actually mean

`RELEASE_ACTIVE_INVALID` is a safety guard, not a version-comparison requirement. Its useful purpose is to refuse silent source/config/executable/manifest corruption of the current immutable release. The defect was that checkpoint 32 treated Python runtime-cache files created after activation as if they were authoritative release mutation. That made a valid same-commit installation unable to converge on rerun.

`INSTALL_ACTION` is the install engine's wrapper saying which governed step failed. It is not the root cause and remains useful for real failures. Checkpoint 33 removes the benign conditions that incorrectly triggered it; it does not suppress genuine failures.

Historical releases are not runtime prerequisites. Normal install/service paths operate on the current/requested commit. Prior releases remain only explicit rollback/update bookkeeping.

## Implemented repair

1. Installer and managed Python services set `PYTHONDONTWRITEBYTECODE=1` and `PYTHONNOUSERSITE=1`.
2. The release manager permits active same-commit repair only when payload-manifest drift consists exclusively of recognized Python cache artifacts. It purges those derived files and immediately revalidates static integrity.
3. Any authoritative mutation remains a hard `RELEASE_ACTIVE_INVALID`; mixed authoritative+cache drift is never auto-repaired.
4. Bluetooth becomes a preferred optional route. A busy/offline requested headset may fall back to exactly one deterministic direct capture and one deterministic non-HDMI playback route. The fallback is reported explicitly and Bluetooth autoconnect can retry later.
5. Zero or ambiguous direct audio still fails closed; no device is guessed.
6. Managed checkpoint-32 application/environment/Bluetooth unit hashes are recognized as legitimate upgrade predecessors after adding bytecode-suppression environment variables.
7. Pi5 GPIO duplicate-name resolution now prefers the unique `pinctrl-rp1` header-controller match without assuming `/dev/gpiochip0`. This covers PTT GPIO17, wake GPIO22, relay GPIO23 and recording LED GPIO27.
8. Curl/remote and `--local-checkpoint` remain two provenance routes into the same bootstrap/install/release engine. Same resolved commit therefore uses the same convergence rules.

## Verification

- Full unit accounting: **46 modules / 476 tests PASS**.
- Full integration accounting: **12 modules / 67 tests PASS**.
- Release lifecycle: **11/11 PASS**.
- Ollama lifecycle: **5/5 PASS**.
- Speech lifecycle: **12/12 PASS**.
- Focused changed-surface suite: PASS.
- RP1 GPIO duplicate-name regressions: PASS.
- Bluetooth-busy + direct USB fallback and no-fallback refusal: PASS.
- Active same-commit cache repair and authoritative-tamper refusal: PASS.
- Managed service predecessor compatibility: PASS.
- Aggregate commands that exceeded an external execution boundary remain recorded as interrupted; only unaccounted cases were rerun.

## Target facts preserved

The project does not restart hardware discovery. Existing target evidence remains: GPIO23 manual fan OFF/ON/OFF works physically; `/dev/i2c-1` exists and the SHT31 answers at `0x44`; USB AIRHUG capture/playback is visible. These are component-level facts, not checkpoint-33 integrated acceptance.

## Evidence boundary and next action

Checkpoint 33 is host/software evidence until installed on the Pi. M10.24 remains open. Install the exact package and require `INSTALLATION_COMPLETE`. If preferred Bluetooth is unavailable but the AIRHUG USB route is still deterministic, installation should continue with direct-audio fallback rather than fail. After completion, proceed directly to GonKen CLI fan control, real SHT31 diagnostics, full-real controller, wake/STT/TTS, fault/reboot/no-login and update/rollback/reinstall acceptance.
