# M3.2 installer state and step protocol

> M3.3 extends this accepted engine with global installed-state paths and a
> separate release activation journal. See `RELEASE_ACTIVATION_SCHEMA.md`.

**Schema revision:** 1

**Scope:** resumable engine mechanics only; no application provisioning

This document defines the durable interface implemented by `scripts/install.sh`
and `scripts/lib/install_engine.sh`. The governing principle is that filesystem,
package, service, model, and artifact probes remain authoritative. A state file
is evidence about an earlier attempt; it is never permission to skip a failed
postcondition.

## 1. M3.2 checkpoint and current engine-only boundary

`bootstrap.sh` creates and validates a private staging directory and then calls:

```bash
scripts/install.sh --source-record /absolute/path/to/source.record
```

At the M3.2 checkpoint—and today when `--engine-only` is explicit—the installer
performs only two bounded actions:

1. revalidate the complete M3.1 record and its advertised Git commit, then write
   a validation marker;
2. write an engine-contract marker confirming that provisioning remains
   forbidden before M3.3.

`--engine-only` returns zero after those steps for deterministic verification
and changes no package, release, virtual environment, model, service,
configuration, or hardware state. Since M3.3, omission of `--engine-only`
continues through the release lifecycle. A development host stops at
`M3_4_TARGET_REQUIRED`; a validated target continues through M3.4 and stops at
`M3_5_UNAVAILABLE`; see `RELEASE_ACTIVATION_SCHEMA.md` and
`OLLAMA_MODEL_LIFECYCLE.md`.

## 2. Private directory layout

```text
<bootstrap-staging>/
├── source.record                         # M3.1 input, mode 0600
└── install-state/                        # mode 0700
    ├── artifacts/                        # real M3.2 postconditions, mode 0700
    │   ├── source-validation.record      # mode 0600
    │   └── engine-contract.record        # mode 0600
    ├── steps/                            # advisory state, mode 0700
    │   ├── source_record_validation.record
    │   └── engine_contract.record
    ├── logs/events/                      # immutable event records, mode 0700
    │   └── <epoch>.<pid>[.<collision>].<sequence>.event
    └── engine.lock/                      # exists only while an invocation owns it
        └── owner.record
```

This staging-local layout applies to `--engine-only`. A full M3.3 installation
uses the same schema under `/var/lib/gonken-agent/install/engine` (or below the
development `--system-root`) so different bootstrap staging directories cannot
bypass the global engine lock.

All directories are owned by the effective installer user and deny group/other
access. Records are written to a same-directory mode-0600 temporary file and
renamed into place. Cooperative signal handling removes registered temporary
files and the owned lock. `SIGKILL` or power loss can leave a lock or a
step-owned partial file; rerun identifies a stale lock and the action must
repair or replace its own partial output.

Atomic rename prevents a half-written record from becoming authoritative. It
does not claim that the whole installation is a transaction, that external
package stores can be rolled back, or that storage survives physical media
failure. M3.3 adds the separate root-owned release activation journal described
in `RELEASE_ACTIVATION_SCHEMA.md`.

## 3. Source-record consumption

The M3.1 `gonken-bootstrap-source-v1` record is parsed line by line. It is never
sourced, evaluated, expanded, or passed through `eval`. The parser rejects:

- a missing, non-regular, or symbolic-link record;
- group/other-readable input or ownership outside the recorded/effective
  administrator transition;
- malformed, duplicate, missing, or unknown fields;
- unknown schema versions, invalid platform mode, user identity, numeric
  fields, source URL/ref, or commit hash;
- development records containing target-like or inconsistent placeholder data.

Before state directories are created, the installer independently rechecks the
kernel, architecture, userspace width, exact Python patch, current resource
gates, non-regressing clock, existing checkout, and advertised source ref. On a
target it also rechecks the Pi model, systemd, `/etc/os-release`, and
`/etc/rpi-issue` fingerprints. If the branch/tag moved, the installer exits
`INSTALL_SOURCE_CHANGED`; the operator must review the new commit and rerun
bootstrap rather than silently installing different code.

## 4. Required step declaration

Each registered step supplies all eight fields:

| Field | Contract |
|---|---|
| Step ID | Stable lowercase identifier, maximum 64 characters |
| Version | Positive integer changed when step semantics change |
| Precondition | Read-only probe deciding whether the action may run |
| Planned mutations | Single-line declaration of intended writes |
| Action | Idempotent mutation function |
| Postcondition | Read-only real-world probe; return 0 satisfied, 1 absent/repairable, greater than 1 probe error |
| Rerun behavior | Explicit repair/skip rule |
| Rollback implication | What may safely be removed or restored |

Missing functions, empty metadata, invalid versions, or duplicate IDs fail
before execution. M3.3 and later steps must use the same interface rather than
introducing ad hoc “already installed” flags.

## 5. Execution algorithm

For every step, in registration order:

1. run the precondition;
2. run the postcondition regardless of advisory state;
3. if the postcondition passes, skip the action and repair missing/stale state;
4. if it returns 1, atomically record `running` and execute the idempotent
   action;
5. run the postcondition again;
6. record `complete` only after the real postcondition passes;
7. otherwise record `failed` and preserve the actionable exit code.

A state record claiming `complete` while its marker is missing or corrupt
causes action and repair. A valid marker with missing/corrupt state causes only
state reconstruction. A repeated successful invocation leaves postcondition
artifacts and already-current complete state byte-identical; it adds a new
immutable event sequence for the new attempt.

## 6. Step-state schema

Every `gonken-install-step-v1` record contains exactly:

```text
format=gonken-install-step-v1
step_id=<stable ID>
step_version=<positive integer>
status=running|complete|failed|interrupted
run_id=<epoch.pid>
observed_epoch=<UTC epoch>
planned_mutations=<declared text>
rerun_behavior=<declared text>
rollback_implication=<declared text>
evidence=<step-defined non-secret identifier>
message=<machine-stable reason>
```

Status meaning:

- `running`: action may not have started or may be partially complete;
- `complete`: the postcondition passed when written, but must be probed again;
- `failed`: the attempt returned a precondition/action/postcondition failure;
- `interrupted`: a cooperative INT, TERM, or HUP was handled.

Abrupt death may leave `running`; that is expected and does not imply failure or
completion.

## 7. Event and lock records

Each `gonken-install-event-v1` file records run ID, sequence, epoch, level,
stable code, step ID, and a content-free machine-stable message. Events are
separate atomic files so an interrupted later write cannot corrupt prior events.
Before writing, the engine checks for an existing epoch/PID run prefix and adds
a numeric collision suffix when necessary. Even immediate reruns with a reused
PID therefore append evidence instead of replacing an earlier event sequence.

The exclusive `gonken-install-lock-v1` record stores PID, Linux boot ID, and
process start ticks. Matching boot/PID/start identity means another invocation
is active. A dead process, prior boot, or reused PID with a different start time
is stale and recoverable. Where a constrained container hides child procfs, the
record uses `process_start_ticks=unavailable` and conservatively checks the PID
with signal 0. Corrupt/unknown lock content is not deleted automatically because
ownership is ambiguous.

## 8. Failure and interruption codes

| Exit | Meaning |
|---:|---|
| 0 | All registered M3.2 postconditions pass under `--engine-only` |
| 64 | Usage or invalid step definition/test control |
| 65 | Invalid, unsafe, inconsistent, or unsupported source record |
| 69 | Required command/source unavailable, source moved, or next milestone unavailable |
| 73 | Private directory or atomic state/log write failure |
| 74 | Action completed without establishing its required postcondition |
| 75 | Cooperative interruption, active installer, or unsafe lock ambiguity |
| 78 | Host/precondition changed or no longer meets the accepted contract |
| Other 1–125 | A step action/precondition code preserved for diagnosis |

Test-only interruption controls are inert unless
`GONKEN_ENABLE_TEST_FAILURES=1`. The tracked fixture then injects TERM or KILL at
declared before/during/after boundaries. Production steps must not enable this
environment gate.

## 9. Deliberate M3.2 limitations

This checkpoint proves the control mechanism, not an installation. It does not:

- install bootstrap prerequisites or clone the resolved source tree;
- create the service account or FHS paths;
- build an immutable release or virtual environment;
- install Python dependencies, Ollama, Qwen, Whisper, Piper, systemd units, or
  hardware rules;
- implement activation, reconciliation, rollback, upgrade, or uninstall;
- establish Raspberry Pi hardware or reboot evidence.

M3.3 implemented the immutable application release and separate activation
journal described here; M3.4 added its bounded Ollama/model steps under the same
global engine lock. The exact next action is M3.5: add verified Whisper/Piper
runtime and artifact provisioning without weakening the existing state,
activation, or model contracts.
