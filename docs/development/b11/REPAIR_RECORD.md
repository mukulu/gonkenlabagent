# B11 target-evidence convergence

Baseline: B10 `b275fa780890300af12828fce9d2ab295c034bcf`, unchanged history.
Current work branch: `dev-unstable/attempt03-b11-convergence`.

## Evidence and scope

FACT: the latest failure bundle identifies qwen3.5:0.8b TOOLS / HTTP 500.
UNLOAD was cleanup and succeeded; it is not the failing operation. Qwen3:0.6b
passed inference/tools; LFM inference passed but its tool result failed validation.
The underlying Ollama server cause remains unresolved; no runtime-pin guess is made.

FACT: B10 applied the real environment configuration before model prerequisites,
but deferred restarting the current environment until after global activation.
On the model error the old B9 daemon therefore continued its simulated actuator.

TARGET OBSERVATION: the supplied manual-recovery transcript identifies the running
B9 interpreter after restart, real SHT31/I2C1/0x44 and real libgpiod/GPIO23,
automatic mode, 28 C ON / 25 C OFF and 60-second dwell. It records automatic ON
18:09:33, OFF 18:10:33 and the `gonken-environment` GPIO consumer. The user confirms
physical motion/stopping. This is scoped evidence for that runtime/configuration,
not B10 installation completion or B11/reboot/voice/display acceptance.

## Decisions and dependency-ready batches

1. Enact Attempt03 section 11.5: require default/selected tools, mark an installed
   alternate TOOL_INCOMPATIBLE rather than aborting for its tool-only error.
   Keep identity, inference, unload and residency checks; deny unqualified tools.
2. Reconcile a compatible existing current environment independently before model
   provisioning, without moving global release activation early. On a fresh target
   without current runtime, defer this optional reconciliation to activation.
   Preserve the user's valid 28/25 policy; never terminate arbitrary GPIO owners.
3. Expose acknowledged relay commands, GPIO ownership and bounded transition/error
   events. Preserve controller/command/physical observation distinctions.
4. Make changes-only watch ignore raw sensor jitter while reporting control,
   quality, configuration and error changes; keep ordinary sample watch available.
5. Run affected and complete current tests, qualify the exact archive, save actual
   source and report remaining blueprint work without manufacturing acceptance.

Raw target bundles/transcripts remain outside Git. Only diagnostic metadata and
synthetic regression cases are exported. Host mocks are not physical evidence.

Execution: implementation in progress, no stable-release promotion.
