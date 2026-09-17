# V09 Checkpoint 43 — Target Failure Chronology and Evidence Ledger

## Scope

This ledger binds the checkpoint-43 implementation cycle to the exact checkpoint-42 package and the 2026-09-17 Raspberry Pi evidence supplied after that package was run. It separates current failure evidence from historical failure codes and from host inference. No row below upgrades host or ZIP evidence into physical acceptance.

## Source register

| Source | SHA-256 | Classification | Use |
|---|---|---|---|
| `gonkenlabagent-v09-single-zip-target-evidence-checkpoint-42-package(1).zip` | `7936c361db246d432ccb5c3f7ef13a01d88fde475fbb24cba65e905d873a268c` | project package | Exact implementation baseline, tag `checkpoint/v09-42-single-zip-target-evidence`, commit `3a0c78e`. |
| `GonKenAgent_V09_CKPT42_to_Single_Evidence_Architecture_Blueprint_Prompt_V2_GOLD.md` | `5ff8e6c141e7f1ef97ea40aaeb8b63acdf9e17f5d6be59651259ada00ff9fad5` | governing implementation prompt | Checkpoint-43 requirements and quality gates. |
| `Pasted text(9).txt` | `6501d848b1cab432876eb04de9f77bd0309a0d3093ff77b85444239025ffe717` | operator console transcript | Ordered installer output and operator workflow. |
| `gonken-install-failure-20260917T134139Z-501602.zip` | `821bb722878244c7d33aa61302d7b731c4d62295b58ea1d1f0c4f70c4a8354e0` | target installer evidence | Failure-stage evidence from checkpoint 42. |
| `gonken-support-20260917T134234Z.zip` | `7ae026ad05739b4091bfe870e8779c57f2218aa62f5485952835f8c811b352b6` | target package support evidence | Installed-system support after the failed install. |
| `gonken-rpi-support-raspberrypi-20260917-145347.zip` | `d9a11cd9b005653c3f7acb49d84845a1e729eb8ba4c5d6a6649525a9a367c34a` | external Raspberry Pi support capture | Additional target context, including the interactive operator audio graph. |

The three target ZIPs are treated as private diagnostic inputs. Only bounded, content-free facts and sanitized regression fixtures are copied into the repository.

## Chronology

| Order | Status | Observation | Consequence |
|---:|---|---|---|
| 1 | VERIFIED | Checkpoint-42 commit `3a0c78e` was fetched and its immutable release built successfully. | Candidate construction was not the immediate failure layer. |
| 2 | VERIFIED | Release activation completed and target GPIO identity completed. | The earlier checkpoint-34 GPIO-alias blocker was passed by this attempt. |
| 3 | VERIFIED | Environment-service, Ollama, Whisper, Piper, speech-smoke, application-service, Bluetooth and runtime-context installer steps were reported satisfied before final readiness. | The failure occurred downstream of these installer postconditions. |
| 4 | VERIFIED | `gonken-agent.service` was systemd `active (running)` but application state remained `STARTING`. | Process liveness was incorrectly insufficient as an operator-level success signal; semantic readiness must remain distinct. |
| 5 | VERIFIED | The fresh wait reason was aggregate `AUDIO_CAPTURE_FAILED`, with `pipewire-usb:AUDIO_CAPTURE_INVALID` and `alsa-usb:AUDIO_CAPTURE_FAILED`. | Checkpoint 43 must localize and repair capture in the exact service context. |
| 6 | VERIFIED | The same bounded journal context still contained prior `WAKE_LED_GPIO_LINE_AMBIGUOUS` lines from an earlier process/attempt. | Current causal failure and historical failure history must be represented separately. |
| 7 | VERIFIED | Package support evidence showed the `gonken-agent` runtime directory plus PipeWire/Pulse socket presence. | Socket existence is structural evidence, not proof that the service account can enumerate and record. |
| 8 | VERIFIED | Additional Raspberry Pi support showed AIRHUG as default source/sink for interactive `gonkenlab`. | Interactive-user success cannot be substituted for service-user capture evidence. |
| 9 | VERIFIED | Installer failure evidence was placed under a root-owned install-failure directory; the operator needed `sudo` to move it. | Evidence output must default to an operator-accessible location and return ownership after sudo. |
| 10 | VERIFIED | The operator then ran `collect-support.sh` separately and obtained a second package support ZIP. | Installer failure must orchestrate canonical support collection into one final ZIP. |

## Failure-family sequence retained from prior target cycles

The project shall preserve this sequence as recurrence knowledge rather than treating each newly exposed blocker as unrelated: release/service virtual-environment dependency mismatch; dirty or mutated Python/release state; stale-release coupling; reboot/pause-state misclassification; Bluetooth treated as more critical than usable deterministic audio; late GPIO discovery; GPIO-chip alias ambiguity; then service-context audio capture failure after the GPIO blocker was removed.

## V/O/I/U/R/E ledger

| Type | Finding |
|---|---|
| V — Verified | The latest Pi attempt failed at semantic appliance readiness with audio capture as the fresh causal dependency. |
| V — Verified | The service process being active did not mean the voice appliance was operationally ready. |
| V — Verified | Checkpoint-42 support and installer-failure evidence were separate artifacts and required a second collection command. |
| O — Observed pattern | Correcting one late installer blocker has repeatedly exposed another dependency at the same final convergence boundary. |
| I — Inference | The quality system therefore needs dependency-wide downstream convergence checks after each blocker is removed, not only a regression test for the repaired error. |
| I — Inference | The PipeWire `AUDIO_CAPTURE_INVALID` result is consistent with a WAV-container finalization/validation boundary; checkpoint 43 therefore changes the PipeWire path to bounded raw PCM capture followed by application-owned canonical WAV construction. Real Pi evidence is still required to prove that this resolves the target failure. |
| U — Unresolved | Whether the exact checkpoint-43 package records successfully through AIRHUG/USB under the `gonken-agent` service identity. |
| U — Unresolved | Full physical SHT31 placement/read campaign, relay/fan motion, wake/acoustic behavior, reboot/no-login and update/rollback on the exact new package. |
| R — Recommendation implemented | Publish freshness-bound semantic readiness with causal component/reason instead of waiting for a generic 180-second timeout. |
| R — Recommendation implemented | Consolidate installer-failure and normal support evidence through one canonical bundle engine. |
| E — Evaluation required | Run the exact qualified checkpoint-43 archive on the real Pi and upload the single emitted evidence ZIP if any target gate still fails. |
