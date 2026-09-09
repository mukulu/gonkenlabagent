# M3.3 immutable release and activation protocol

**Status:** Implemented on `dev/bootstrap-rearchitecture`

**Implementation commit:** `0ea9db1` (`feat: add immutable release activation lifecycle`)

**Evidence boundary:** deterministic T0/T1 host evidence; physical Raspberry Pi,
real power-loss, service-start, and online artifact evidence remain blocked.

## 1. Purpose and boundary

M3.3 converts the exact commit admitted by M3.1 into a validated immutable
application release and activates it without making a partially built candidate
live. It reuses the M3.2 probe-authoritative step engine. It does not install
Ollama, Qwen, Whisper, Piper, systemd units, configuration, corpus data, audio,
GPIO, wake-word, or power-control components.

`M3_3_RELEASE_COMPLETE` therefore means only that the maintained core package
and release-control helpers are installed and post-verified. It is not
`SOFTWARE_READY`, `SOFTWARE_READY_HARDWARE_DEGRADED`, or `READY`.

## 2. Installed paths and ownership

| Path | Purpose | Target ownership/mode |
|---|---|---|
| `/usr/local/lib/gonken-agent/releases/<commit>/` | Immutable release-local venv and maintenance helpers | root-owned; no write bits |
| `/usr/local/lib/gonken-agent/current` | Atomic relative link to `releases/<commit>` | root-owned release namespace |
| `/usr/local/bin/gonken-agent` | Constant relative link through `current` to the CLI | root-owned symlink |
| `/var/lib/gonken-agent/install/` | Private activation state and maintenance lock | root-owned, `0700` |
| `/var/lib/gonken-agent/install/engine/` | M3.2 global installer state/lock | root-owned, `0700` |
| `/var/lib/gonken-agent/install/logs/` | Immutable content-free step events | root-owned, private |

The production runtime account is `gonken-agent`, a system account with home
`/var/lib/gonken-agent` and shell `/usr/sbin/nologin`. It owns neither release
code nor activation state. Final pre-activation and post-switch smoke checks
execute as that account when the installer is root; construction-time smoke
runs before the root-owned candidate is exposed outside its private workspace.

Development mode maps the same FHS paths below an explicit/private
`--system-root` and uses the invoking account for smoke checks. It is test
evidence only and never changes the production paths.

## 3. Source and candidate construction

The installer reparses the private `source.record` as data, revalidates current
host facts and the advertised ref, and requires the ref still to resolve to its
recorded 40-character commit. Candidate construction then:

1. fetches the requested ref into a private, identity-scoped bare repository;
2. verifies `FETCH_HEAD^{commit}` equals the recorded commit;
3. rejects Git submodules and unsafe archive members, including links, devices,
   absolute paths, and traversal;
4. selects the platform profile (`dev-py312` or
   `core-pi-trixie-py313`) and hashes its exact lock;
5. builds one wheel from that source commit with the distribution-provided
   setuptools backend and records the backend version and wheel hash;
6. creates a release-local venv, installs the exact/hash lock with no index,
   and installs only the locally built wheel with `--no-deps`;
7. strips inherited `PYTHONPATH`/`PYTHONHOME` and disables user-site loading for
   all subprocess validation;
8. validates CLI version, JSON status product identity, and `pip check`;
9. copies the release/reconciliation helpers from the same exact source commit;
10. records payload size and a deterministic payload digest, removes all write
    bits, and renames the candidate atomically into `releases/<commit>`.

The distribution setuptools version is recorded but is not a project hash-lock:
it is a target bootstrap prerequisite managed by APT. Runtime dependencies are
still governed by the exact/hash lock. This distinction must be reassessed if a
future source build requires any other build dependency.

The minimum release headroom is the greater of 512 MiB or twice the largest
existing release plus 256 MiB. This is a conservative construction guard, not a
model-storage estimate and not Pi performance evidence.

## 4. Release record

Each final release contains read-only `release.record` using
`format=gonken-release-v1` and exactly these fields:

- `commit`, `profile`, `python_version`, and `package_version`;
- `lock_sha256`, `wheel_sha256`, `maintenance_sha256`, and `payload_sha256`;
- `build_backend`, `owner_uid`, `payload_size_kib`, and `built_epoch`;
- `validation=passed`.

Validation rejects a path/commit/profile disagreement, malformed record,
invalid digest/numeric field, changed maintenance helper or payload, any
writable non-symlink object, ownership drift, failed CLI/status/pip smoke, or
package-version disagreement. Existing invalid final releases are not silently
overwritten or deleted.

## 5. Activation journal and pointer

`activation.record` uses `format=gonken-activation-v1` and exactly:
`candidate_commit`, `previous_commit`, `phase`, `observed_epoch`, and `message`.
The only phases are:

| Phase | Durable meaning |
|---|---|
| `prepared` | Candidate and previous identity were recorded after candidate prevalidation; switch may not have happened. |
| `switched` | `current` was durably replaced with the candidate; post-switch validation is pending. |
| `post_verified` | Pointer and candidate agree and service-user smoke checks passed after switching. |
| `rolled_back` | Candidate failed and `current` was restored to the recorded previous release, or removed if none existed. |

Journal records and the `current` symlink use same-directory temporary files,
`os.replace`, and parent-directory `fsync`. The pointer is accepted only when it
is exactly `releases/<40-lowercase-hex-commit>`; absolute and escaping targets
fail closed. Activation/reconciliation/status share a nonblocking
`maintenance.lock`, while a full installer invocation also holds the global
M3.2 engine lock.

## 6. Reconciliation and rollback

`scripts/reconcile-release.sh` invokes the standard-library release manager and
is copied into every release under `maintenance/`. M6 will wire the installed
copy into `ExecStartPre`; M3.3 only supplies and validates the command.

Reconciliation follows journal plus pointer truth:

- no journal and no pointer is an empty installation;
- a final journal/pointer disagreement is ambiguous and requires inspection;
- a valid `prepared` candidate is switched and post-checked;
- an invalid prepared or post-switch candidate is rolled back;
- a valid `switched` candidate completes its post-check and journal;
- `post_verified` and `rolled_back` states must agree with the pointer and
  revalidate the referenced release.

After a successful activation, pruning retains exactly the active release and
its recorded previous release. An older inactive release is fully validated
before its owned directories are made removable and deleted. Corrupt inactive
evidence stops pruning for manual review.

## 7. Interruption and rerun behavior

Test-only failure injection is inert unless
`GONKEN_ENABLE_TEST_FAILURES=1`. The deterministic suite interrupts
before/during/after candidate finalization, journal replacement, `current`
replacement, and post-switch validation. Rerun must converge to one of two
truthful outcomes: a valid candidate becomes `post_verified`, or the recorded
previous valid release becomes `rolled_back`.

A narrow crash interval after the candidate rename but before its top directory
loses write permission is repaired only when commit/profile, complete payload
digest, descendant immutability, and ownership all match. Other invalid final
states fail closed.

Host TERM/KILL tests approximate interruption semantics; they do not prove
storage durability under real power removal. Controlled Pi power-loss tests
remain a T6 requirement.

## 8. Stable failures

Important failure families include `RELEASE_SPACE`, `RELEASE_SOURCE_CHANGED`,
`RELEASE_SOURCE`, `RELEASE_BUILD`, `RELEASE_COMMAND`, `RELEASE_INVALID`,
`RELEASE_MUTABLE`, `RELEASE_OWNER`, `RELEASE_SMOKE`, `ACTIVATION_BUSY`,
`ACTIVATION_POINTER`, `ACTIVATION_JOURNAL`, `ACTIVATION_AMBIGUOUS`, and
`ACTIVATION_INCOMPLETE`. Every emitted error includes `code`, `message`, and
`remediation`. A failure must be corrected or reconciled and then rerun; state
records must never be edited to manufacture success.

## 9. Exact next action

M3.4 now consumes its manager/manifest/unit inputs from the active immutable
release; see `OLLAMA_MODEL_LIFECYCLE.md`. Implement M3.5 only: verified
Whisper/Piper runtime and artifact provisioning, sample STT/TTS smoke, damaged
pair recovery, and second-run convergence. Do not advance to the GonKen systemd
application service, audio/GPIO rules, wake word, power controls, or readiness
claims until M3.5 passes.
