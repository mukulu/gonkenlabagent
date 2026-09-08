# Physical and manual test probes

Nothing in this directory is part of the automated T0/T1 suite. These programs
can open microphones, play audio, load large local models, or wait for a person.
They therefore require explicit opt-in and physical supervision.

The current programs exercise only the quarantined source-compatibility
runtime. They do not establish Raspberry Pi release readiness, and the legacy
wake probe is not an X1 “Hey Gonken” evaluation. It deliberately advertises no
spoken phrase because the loaded compatibility model may not match the desired
phrase.

Run only after provisioning the repository-owned compatibility `.venv`:

```bash
GONKEN_RUN_HARDWARE_TESTS=1 .venv/bin/python \
  tests/hardware/audio_pipeline_manual.py

GONKEN_RUN_HARDWARE_TESTS=1 .venv/bin/python \
  tests/hardware/wake_word_manual.py
```

Before recording a result, document the commit, Pi model/RAM, OS image, kernel,
architecture, Python, power supply, cooling, configured devices, and date in
`docs/development/TEST_MATRIX.md`. A person must verify audibility and wiring;
an exit code alone does not prove those physical qualities.
