"""Dependency-light command-line boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from . import IDENTITY, __version__
from .compat import CompatibilityError, run_legacy_source
from .config import ConfigError, load_config, migrate_legacy, parse_cli_overrides


EXIT_FAILED = 1
EXIT_UNSUPPORTED = 3


def _status() -> dict[str, object]:
    ready_file = Path("/run/gonken-agent/ready.json")
    runtime_ready = False
    wake_phrase = "GonKen"
    try:
        if ready_file.is_file() and not ready_file.is_symlink() and ready_file.stat().st_size <= 8192:
            payload = json.loads(ready_file.read_text(encoding="utf-8"))
            runtime_ready = payload.get("status") == "READY" and payload.get("code") == "VOICE_RUNTIME_READY"
            if isinstance(payload.get("wake_phrase"), str) and payload["wake_phrase"].strip():
                wake_phrase = payload["wake_phrase"]
    except (OSError, ValueError, json.JSONDecodeError):
        runtime_ready = False
    return {
        "product": IDENTITY.product_name,
        "package": IDENTITY.package_name,
        "version": __version__,
        "package_foundation": "complete",
        "configuration_foundation": "complete",
        "core_runtime_ready": runtime_ready,
        "text_diagnostics": "available",
        "voice_runtime": "ready" if runtime_ready else "waiting_or_stopped",
        "wake_phrase": wake_phrase,
        "redistribution_approved": False,
        "redistribution_policy": "prohibited",
        "extensions": {
            "wake_word": "enabled",
            "voice_power": "disabled",
            "lan_dashboard": "disabled",
            "bluetooth": (
                "configured"
                if Path("/etc/gonken-agent/bluetooth-device.record").is_file()
                else "disabled"
            ),
        },
    }



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gonken-agent",
        description=f"{IDENTITY.product_name} development CLI",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("version", help="print the package version")

    status_parser = subparsers.add_parser(
        "status", help="show the implementation boundary"
    )
    status_parser.add_argument("--json", action="store_true", dest="as_json")

    wake_parser = subparsers.add_parser("wake", help="inspect wake phrase and matcher boundary")
    wake_commands = wake_parser.add_subparsers(dest="wake_command", required=True)
    wake_status = wake_commands.add_parser("status", help="show configured wake phrase and host matcher metadata")
    wake_status.add_argument("--json", action="store_true", dest="as_json")

    run_parser = subparsers.add_parser(
        "run", help="run an available runtime entry point"
    )
    run_parser.add_argument(
        "--legacy-source",
        action="store_true",
        help="explicitly use the pre-package source runtime",
    )

    from .operations import config_arguments
    config_arguments(run_parser)
    run_parser.add_argument('--text-only', action='store_true', help='read diagnostic questions from stdin; no audio capture')
    run_parser.add_argument('--index', type=Path)
    run_parser.add_argument('--extractive', action='store_true')
    run_parser.add_argument('--telemetry', type=Path)
    run_parser.add_argument('--with-dashboard', action='store_true')

    talk_parser = subparsers.add_parser(
        'talk', help='run one manual microphone -> local AI -> speaker turn'
    )
    config_arguments(talk_parser)
    talk_parser.add_argument(
        '--seconds', type=int, default=8,
        help='bounded microphone capture window in seconds (default: 8)',
    )

    components_parser = subparsers.add_parser(
        "components", help="show independent voice/model/environment/sensor/fan/tool states"
    )
    components_parser.add_argument("--json", action="store_true", dest="as_json")
    components_parser.add_argument("--require-ready", action="store_true", help="require fresh selected-profile component readiness; never physical acceptance")
    config_arguments(components_parser)

    llm_parser = subparsers.add_parser("llm", help="inspect and administer the governed local-model roster")
    config_arguments(llm_parser)
    llm_commands = llm_parser.add_subparsers(dest="llm_command", required=True)
    for name, help_text in (("status", "show active model and roster health"), ("models", "list governed models and installation state")):
        leaf = llm_commands.add_parser(name, help=help_text)
        leaf.add_argument("--json", action="store_true", dest="as_json")
    capabilities = llm_commands.add_parser("capabilities", help="run a non-mutating typed-tool capability smoke")
    capabilities.add_argument("--model")
    capabilities.add_argument("--all", action="store_true", dest="all_models", help="check every governed roster model")
    capabilities.add_argument("--thinking", action="store_true", help="run semantic capability cases with thinking enabled")
    capabilities.add_argument("--json", action="store_true", dest="as_json")
    benchmark = llm_commands.add_parser("benchmark", help="run a bounded content-free model latency benchmark")
    benchmark.add_argument("--model")
    benchmark.add_argument("--iterations", type=int, default=3)
    benchmark.add_argument("--thinking", action="store_true", help="benchmark the model with thinking enabled")
    benchmark.add_argument("--json", action="store_true", dest="as_json")
    switch = llm_commands.add_parser("switch", help="atomically switch the voice service to an admitted model with rollback")
    switch.add_argument("model")
    switch.add_argument("--json", action="store_true", dest="as_json")

    _add_environment_commands(subparsers)

    config_parser = subparsers.add_parser(
        "config", help="inspect or migrate validated configuration"
    )
    config_commands = config_parser.add_subparsers(dest="config_command", required=True)
    show_parser = config_commands.add_parser(
        "show", help="show validated effective configuration"
    )
    show_parser.add_argument(
        "--effective", action="store_true", required=True,
        help="confirm that merged values rather than a source file are requested",
    )
    show_parser.add_argument("--json", action="store_true", dest="as_json")
    show_parser.add_argument(
        "--show-paths", action="store_true",
        help="include effective filesystem paths (default output redacts paths)",
    )
    show_parser.add_argument(
        "--site", type=Path, help="site TOML (default: /etc/gonken-agent/config.toml)"
    )
    show_parser.add_argument("--no-site", action="store_true")
    show_parser.add_argument(
        "--set", action="append", default=[], metavar="SECTION.FIELD=VALUE",
        help="apply a one-shot non-persistent override",
    )

    migrate_parser = config_commands.add_parser(
        "migrate", help="stage a validated site TOML from legacy inputs"
    )
    migrate_parser.add_argument(
        "--legacy-json", type=Path, default=Path("config/config.json")
    )
    migrate_parser.add_argument("--legacy-env", type=Path, default=Path(".env"))
    migrate_parser.add_argument("--output", type=Path, required=True)
    migrate_parser.add_argument("--backup-dir", type=Path)
    migrate_parser.add_argument("--json", action="store_true", dest="as_json")
    from .operations import add_commands
    add_commands(subparsers)
    return parser


def _service_is_active() -> bool:
    try:
        return subprocess.run(
            ["/usr/bin/systemctl", "is-active", "--quiet", "gonken-agent.service"],
            check=False, capture_output=True, timeout=3,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the CLI and return a stable process exit code."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command in {'index', 'ask', 'doctor', 'dashboard', 'support', 'service'}:
        from .operations import execute
        try:
            return execute(args)
        except (ValueError, OSError, RuntimeError) as exc:
            # Exception messages may contain corpus paths or content. Keep diagnostics categorical.
            print(json.dumps({'status': 'FAILED', 'code': 'LOCAL_OPERATION_FAILED',
                              'error_type': type(exc).__name__}), file=sys.stderr)
            return EXIT_FAILED
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "version":
        print(__version__)
        return 0
    if args.command == "status":
        status = _status()
        if args.as_json:
            print(json.dumps(status, sort_keys=True))
        else:
            print(f"{status['product']} {status['version']}")
            print(f"Voice runtime: {status['voice_runtime']}")
            print(f"Wake phrase: {status['wake_phrase']}")
            print("Redistribution: prohibited; no project license is granted")
            print(f"Bluetooth: {status['extensions']['bluetooth']}")
        return 0
    if args.command == "wake":
        return _execute_wake_command(args)
    if args.command == "components":
        try:
            from .operations import effective
            from .component_status import collect, required_ready
            config = effective(args)
            payload = collect(config)
        except (ValueError, OSError, RuntimeError, ConfigError) as exc:
            print(json.dumps({"status": "FAILED", "code": "COMPONENT_STATUS_FAILED", "error_type": type(exc).__name__}), file=sys.stderr)
            return EXIT_FAILED
        if args.as_json:
            print(json.dumps(payload, sort_keys=True))
        else:
            for name, row in payload["components"].items():
                print(f"{name}: {row['status']} ({row['code']})")
            print("physical_motion_observed=false software_speed_control=false physical_acceptance=false")
        return EXIT_FAILED if args.require_ready and not required_ready(config, payload) else 0
    if args.command == "llm":
        try:
            from .operations import effective
            from .llm import admin as llm_admin
            config = effective(args)
            command = args.llm_command
            if command in {"status", "models"}:
                payload = llm_admin.status(config)
            elif command == "capabilities":
                if args.all_models and args.model:
                    raise ValueError("--all and --model cannot be combined")
                if args.all_models:
                    payload = llm_admin.all_model_capabilities(config, thinking=args.thinking)
                else:
                    model = args.model or llm_admin.status(config)["selection"]["model"]
                    payload = llm_admin.capability_report(config, str(model), thinking=args.thinking)
            elif command == "benchmark":
                model = args.model or llm_admin.status(config)["selection"]["model"]
                payload = llm_admin.benchmark(config, str(model), args.iterations, thinking=args.thinking)
            elif command == "switch":
                payload = llm_admin.switch(config, args.model)
            else:
                raise ValueError("unsupported llm command")
        except (ValueError, OSError, RuntimeError, ConfigError) as exc:
            code = getattr(exc, "code", "LLM_ADMIN_FAILED")
            print(json.dumps({"status": "FAILED", "code": code, "error_type": type(exc).__name__}), file=sys.stderr)
            return EXIT_FAILED
        if args.as_json:
            print(json.dumps(payload, sort_keys=True))
        else:
            if command in {"status", "models"}:
                selection = payload["selection"]
                print(f"Active model: {selection['model']}  generation={selection['generation']}")
                for row in payload["roster"]:
                    marker = "*" if row["selected"] else " "
                    print(f"{marker} {row['tag']}: installed={row['installed']} tools={row['tool_call_smoke']} role={row['role']}")
            elif command == "benchmark":
                print(f"Model: {payload['model']}  iterations={payload['iterations']}  median_wall_ms={payload['wall_ns']['median'] / 1_000_000:.1f}")
            elif command == "capabilities":
                if args.all_models:
                    print(f"Roster tool capability: {payload['status']}  models={len(payload['models'])}  thinking={payload['thinking']}")
                    for row in payload["models"]:
                        semantic = row["semantic_tool_quality"]
                        print(f"  {row['model']}: {row['status']} semantic={semantic['passed']}/{semantic['total']}")
                else:
                    semantic = payload["semantic_tool_quality"]
                    print(f"Model: {payload['model']}  typed-tool capability: {payload['status']}  semantic={semantic['passed']}/{semantic['total']}")
            else:
                print(f"Active model: {payload['model']}  previous={payload['previous_model']} changed={payload['changed']}")
        return 0
    if args.command == "run":
        if args.text_only:
            if args.legacy_source:
                parser.error('--text-only and --legacy-source cannot be combined')
            from .operations import text_session
            try:
                return text_session(args)
            except (ValueError, OSError, RuntimeError) as exc:
                print(json.dumps({'status': 'FAILED', 'code': 'TEXT_SESSION_FAILED', 'error_type': type(exc).__name__}), file=sys.stderr)
                return EXIT_FAILED
        if args.legacy_source:
            try:
                return run_legacy_source()
            except CompatibilityError as exc:
                print(f"Cannot start compatibility runtime: {exc}", file=sys.stderr)
                return EXIT_FAILED
        if _service_is_active():
            print("gonken-agent.service is already running. Say the wake phrase, or stop the service before foreground run.", file=sys.stderr)
            return 2
        from .operations import effective
        from .voice_runtime import run_appliance
        try:
            return run_appliance(effective(args), foreground=True)
        except (ValueError, OSError, RuntimeError) as exc:
            print(json.dumps({'status':'FAILED','code':'VOICE_RUNTIME_FAILED','error_type':type(exc).__name__}), file=sys.stderr)
            return EXIT_FAILED
    if args.command == 'talk':
        if not 1 <= args.seconds <= 30:
            parser.error('--seconds must be between 1 and 30')
        if _service_is_active():
            print("gonken-agent.service is already running. Say the wake phrase, or stop the service before manual talk.", file=sys.stderr)
            return 2
        from .operations import effective
        from .voice_runtime import run_appliance
        try:
            return run_appliance(effective(args), one_turn=True, seconds=args.seconds, foreground=True)
        except (ValueError, OSError, RuntimeError) as exc:
            print(json.dumps({'status':'FAILED','code':'VOICE_TALK_FAILED','error_type':type(exc).__name__}), file=sys.stderr)
            return EXIT_FAILED
    if args.command == "env":
        return _execute_environment_command(args)
    if args.command == "config":
        try:
            if args.config_command == "show":
                if args.site is not None and args.no_site:
                    raise ConfigError("--site and --no-site cannot be combined")
                overrides = parse_cli_overrides(args.set)
                if args.no_site:
                    effective = load_config(site_path=None, cli_overrides=overrides)
                elif args.site is not None:
                    effective = load_config(site_path=args.site, cli_overrides=overrides)
                else:
                    effective = load_config(cli_overrides=overrides)
                if args.as_json:
                    print(json.dumps({
                        "config": effective.as_dict(redact=not args.show_paths),
                        "sources": effective.source_dict(),
                    }, sort_keys=True))
                else:
                    _print_effective_config(
                        effective.as_dict(redact=not args.show_paths), effective.sources
                    )
                return 0
            if args.config_command == "migrate":
                result = migrate_legacy(
                    legacy_json=args.legacy_json,
                    legacy_env=args.legacy_env,
                    output=args.output,
                    backup_dir=args.backup_dir,
                )
                payload = {
                    "backups": [str(path) for path in result.backups],
                    "changed": result.changed,
                    "ignored": list(result.ignored),
                    "output": str(result.output),
                }
                if args.as_json:
                    print(json.dumps(payload, sort_keys=True))
                else:
                    state = "created" if result.changed else "already current"
                    print(f"Migration output {state}: {result.output}")
                    for backup in result.backups:
                        print(f"Legacy backup: {backup}")
                    for ignored in result.ignored:
                        print(f"Recognized but not part of offline core: {ignored}")
                return 0
        except (ConfigError, OSError) as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return EXIT_FAILED

    parser.error(f"unsupported command: {args.command}")
    return EXIT_UNSUPPORTED


def _execute_wake_command(args: argparse.Namespace) -> int:
    if args.wake_command != "status":
        raise ValueError("unsupported wake command")
    try:
        effective = load_config()
        from .voice_runtime import (
            WAKE_CAPTURE_MODE,
            WAKE_CAPTURE_QUEUE_SIZE,
            WAKE_CAPTURE_WINDOW_SECONDS,
            WAKE_MATCHER_VERSION,
            wake_matcher_aliases,
        )

        phrase = effective.config.extensions.wake_word.phrase
        payload = {
            "status": "READY_FOR_HOST_MATCHING",
            "wake_phrase": phrase,
            "wake_matcher_version": WAKE_MATCHER_VERSION,
            "aliases": wake_matcher_aliases(phrase),
            "matching": {
                "unicode_case_punctuation_normalization": True,
                "adjacent_token_joining": True,
                "bounded_one_edit_for_gonken_like_tokens": True,
                "hey_gonken_alias": True,
            },
            "capture": {
                "mode": WAKE_CAPTURE_MODE,
                "window_seconds": WAKE_CAPTURE_WINDOW_SECONDS,
                "queue_size": WAKE_CAPTURE_QUEUE_SIZE,
                "capture_continues_during_transcription": True,
                "backlog_policy": "drop_stale_keep_newest",
            },
            "monitoring_indicator": {
                "logical_bcm": effective.config.extensions.wake_word.monitoring_led_gpio,
                "line_resolution": "gpio_line_name",
                "target_mapping": "NOT_RUN",
                "physical_visibility": "NOT_RUN",
            },
            "physical_evidence": False,
            "real_wake_acceptance": "NOT_RUN",
        }
    except (ConfigError, OSError) as exc:
        print(f"Wake configuration error: {exc}", file=sys.stderr)
        return EXIT_FAILED
    if args.as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"Wake phrase: {payload['wake_phrase']}")
        print(f"Matcher: {payload['wake_matcher_version']}")
        print("Aliases: " + ", ".join(str(alias) for alias in payload["aliases"]))
        print(f"Capture: {payload['capture']['mode']} window={payload['capture']['window_seconds']}s queue={payload['capture']['queue_size']}")
        print(f"Wake-monitoring LED: logical BCM{payload['monitoring_indicator']['logical_bcm']} target mapping=NOT_RUN")
        print("Physical wake acceptance: NOT_RUN")
    return 0


def _add_env_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        default=argparse.SUPPRESS,
        help="emit machine-readable JSON",
    )


def _add_environment_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    env_parser = subparsers.add_parser(
        "env",
        help="inspect and control the room-environment daemon through local IPC",
    )
    env_parser.add_argument(
        "--socket",
        type=Path,
        help="environment control socket (default: effective configuration)",
    )
    env_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit machine-readable JSON",
    )
    env_commands = env_parser.add_subparsers(dest="env_command", required=True)

    serve = env_commands.add_parser(
        "serve",
        help=argparse.SUPPRESS,
        description="run the room-environment daemon when the static hardware profile is enabled",
    )
    serve.add_argument(
        "--site", type=Path, help="site TOML (default: /etc/gonken-agent/config.toml)"
    )
    serve.add_argument("--no-site", action="store_true")
    serve.add_argument(
        "--check",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    _add_env_json_flag(serve)

    for name, help_text in (
        ("status", "show environment state and capability boundary"),
        ("health", "show environment service health"),
        ("temperature", "read and report current temperature"),
        ("humidity", "read and report current relative humidity"),
        ("read", "read and report temperature and humidity"),
        ("probe", "run a bounded non-destructive environment probe"),
    ):
        leaf = env_commands.add_parser(name, help=help_text)
        _add_env_json_flag(leaf)

    watch = env_commands.add_parser("watch", help="watch live environment readings through local IPC")
    watch.add_argument("--interval", type=float, default=2.0, help="seconds between samples; default 2.0")
    watch.add_argument("--count", type=int, help="optional number of samples, mainly for bounded runs/tests")
    watch.add_argument("--once", action="store_true", help="emit one passive snapshot and exit")
    watch.add_argument("--changes-only", action="store_true", help="emit only when meaningful environment state changes")
    watch.add_argument("--health", action="store_true", help="attach read-only daemon health to each emitted sample")
    _add_env_json_flag(watch)

    fan_parser = env_commands.add_parser("fan", help="set room-fan relay power")
    fan_commands = fan_parser.add_subparsers(dest="fan_command", required=True)
    fan_on = fan_commands.add_parser("on", help="request fan relay power on through the daemon")
    _add_env_json_flag(fan_on)
    fan_off = fan_commands.add_parser("off", help="request fan relay power off through the daemon")
    _add_env_json_flag(fan_off)

    mode_parser = env_commands.add_parser("mode", help="set room-fan operating mode")
    mode_commands = mode_parser.add_subparsers(dest="mode_command", required=True)
    mode_set = mode_commands.add_parser("set", help="set mode: manual, semi-automatic, automatic, disabled")
    mode_set.add_argument("mode")
    _add_env_json_flag(mode_set)

    policy_parser = env_commands.add_parser("policy", help="show or update mutable fan policy")
    policy_commands = policy_parser.add_subparsers(dest="policy_command", required=True)
    policy_show = policy_commands.add_parser("show", help="show mutable fan policy and static bounds")
    _add_env_json_flag(policy_show)
    policy_set = policy_commands.add_parser("set", help="update mutable fan policy through the daemon")
    policy_set.add_argument("--expected-generation", type=int)
    policy_set.add_argument("--mode")
    policy_set.add_argument("--start-c", type=float)
    policy_set.add_argument("--stop-c", type=float)
    policy_set.add_argument("--minimum-on-seconds", type=int)
    policy_set.add_argument("--minimum-off-seconds", type=int)
    _add_env_json_flag(policy_set)

    simulate_parser = env_commands.add_parser(
        "simulate",
        help="inspect or mutate daemon-owned simulation state through local IPC",
    )
    simulate_commands = simulate_parser.add_subparsers(dest="simulate_command", required=True)

    simulate_status = simulate_commands.add_parser("status", help="show simulation state and provenance")
    _add_env_json_flag(simulate_status)
    simulate_reset = simulate_commands.add_parser("reset", help="reset simulated sensor and actuator state")
    _add_env_json_flag(simulate_reset)

    simulate_sensor = simulate_commands.add_parser("sensor", help="control simulated sensor state")
    simulate_sensor_commands = simulate_sensor.add_subparsers(dest="simulate_sensor_command", required=True)
    sensor_set = simulate_sensor_commands.add_parser("set", help="set simulated temperature and humidity")
    sensor_set.add_argument("--temperature-c", type=float, required=True)
    sensor_set.add_argument("--humidity-pct", type=float, required=True)
    _add_env_json_flag(sensor_set)
    for sensor_fault, help_text in (
        ("unavailable", "make the simulated sensor unavailable"),
        ("crc-error", "make the simulated sensor report a CRC failure"),
    ):
        sensor_fault_parser = simulate_sensor_commands.add_parser(sensor_fault, help=help_text)
        _add_env_json_flag(sensor_fault_parser)
    sensor_stale = simulate_sensor_commands.add_parser("stale", help="make the simulated sensor reading stale")
    sensor_stale.add_argument("--age-seconds", type=float, required=True)
    _add_env_json_flag(sensor_stale)
    sensor_recover = simulate_sensor_commands.add_parser("recover", help="recover the simulated sensor with a valid reading")
    sensor_recover.add_argument("--temperature-c", type=float, required=True)
    sensor_recover.add_argument("--humidity-pct", type=float, required=True)
    _add_env_json_flag(sensor_recover)
    sensor_reset = simulate_sensor_commands.add_parser("reset", help="reset simulated sensor state")
    _add_env_json_flag(sensor_reset)

    simulate_fan = simulate_commands.add_parser("fan", help="inspect or fault the simulated fan actuator")
    simulate_fan_commands = simulate_fan.add_subparsers(dest="simulate_fan_command", required=True)
    fan_show = simulate_fan_commands.add_parser("show", help="show simulated fan actuator state")
    _add_env_json_flag(fan_show)
    fan_behavior = simulate_fan_commands.add_parser("behavior", help="set simulated actuator behavior")
    fan_behavior.add_argument("behavior", choices=("normal", "unavailable", "fail-next-write"))
    _add_env_json_flag(fan_behavior)
    for fan_fault, help_text in (
        ("unavailable", "make the simulated fan actuator unavailable"),
        ("fail-next-write", "make the next simulated actuator write fail"),
        ("reset", "reset simulated fan actuator state"),
    ):
        fan_fault_parser = simulate_fan_commands.add_parser(fan_fault, help=help_text)
        _add_env_json_flag(fan_fault_parser)


def _execute_environment_command(args: argparse.Namespace) -> int:
    if args.env_command == "serve":
        return _run_environment_daemon(args)
    if args.env_command == "watch":
        return _run_environment_watch(args)
    try:
        client = _environment_client_from_args(args)
        payload = _call_environment_command(client, args)
    except ConfigError as exc:
        return _environment_error("ENV_CONFIG_FAILED", _environment_public_message(exc), args.as_json)
    except OSError as exc:
        return _environment_error("ENV_CLI_FAILED", type(exc).__name__, args.as_json)
    except ValueError as exc:
        return _environment_error("ENV_CLI_FAILED", _environment_public_message(exc), args.as_json)
    except Exception as exc:
        code = getattr(exc, "code", "ENV_CALL_FAILED")
        return _environment_error(str(code), _environment_public_message(exc), args.as_json)

    if args.as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        _print_environment_payload(args, payload)
    return 0



def _run_environment_watch(args: argparse.Namespace) -> int:
    try:
        if args.interval < 0:
            raise ValueError("watch interval must be non-negative")
        if args.count is not None and args.count < 1:
            raise ValueError("watch count must be positive")
        if args.once and args.count not in (None, 1):
            raise ValueError("--once cannot be combined with --count other than 1")
        limit = 1 if args.once else args.count
        client = _environment_client_from_args(args)
        observed = 0
        emitted = 0
        previous_signature = None
        while True:
            # Watch is deliberately passive: it observes daemon-owned snapshots.
            # It never directly reads I2C or writes the actuator.
            raw = client.snapshot()  # type: ignore[attr-defined]
            payload = dict(raw)
            if args.health:
                payload["health"] = client.health()  # type: ignore[attr-defined]
            signature = _environment_watch_signature(payload)
            should_emit = not args.changes_only or previous_signature is None or signature != previous_signature
            if should_emit:
                if args.as_json:
                    print(json.dumps(payload, sort_keys=True), flush=True)
                else:
                    _print_environment_watch_row(payload)
                emitted += 1
            previous_signature = signature
            observed += 1
            if limit is not None and observed >= limit:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    except ConfigError as exc:
        return _environment_error("ENV_CONFIG_FAILED", _environment_public_message(exc), args.as_json)
    except OSError as exc:
        return _environment_error("ENV_CLI_FAILED", type(exc).__name__, args.as_json)
    except ValueError as exc:
        return _environment_error("ENV_CLI_FAILED", _environment_public_message(exc), args.as_json)
    except Exception as exc:
        code = getattr(exc, "code", "ENV_CALL_FAILED")
        return _environment_error(str(code), _environment_public_message(exc), args.as_json)


def _run_environment_daemon(args: argparse.Namespace) -> int:
    try:
        if getattr(args, "site", None) is not None and getattr(args, "no_site", False):
            raise ConfigError("--site and --no-site cannot be combined")
        if getattr(args, "no_site", False):
            effective = load_config(site_path=None)
        elif getattr(args, "site", None) is not None:
            effective = load_config(site_path=args.site)
        else:
            effective = load_config()
        env = effective.config.extensions.environment
    except ConfigError as exc:
        return _environment_error("ENV_CONFIG_FAILED", _environment_public_message(exc), getattr(args, "as_json", False))

    if not env.enabled:
        payload = {
            "status": "DISABLED",
            "code": "ENVIRONMENT_DISABLED",
            "enabled": False,
            "socket_path": env.socket_path,
            "policy_path": env.policy_path,
            "physical_evidence": False,
            "hardware_toggled": False,
        }
        if getattr(args, "as_json", False):
            print(json.dumps(payload, sort_keys=True))
        else:
            print("[OK] code=ENVIRONMENT_DISABLED enabled=false hardware_toggled=false")
        return 0

    try:
        from .environment import EnvironmentDaemon, EnvironmentDaemonError, build_environment_service_core
        if getattr(args, "check", False):
            core = build_environment_service_core(env, initialize_policy=False)
            payload = {
                "status": "READY",
                "code": "ENVIRONMENT_DAEMON_CONFIG_OK",
                "enabled": True,
                "socket_path": env.socket_path,
                "policy_path": env.policy_path,
                "physical_evidence": False,
                "hardware_toggled": False,
                "daemon": core.daemon_metadata(),
            }
            # ``--check`` is a construction/configuration check only.  The
            # V09 simulation/HIL plan explicitly forbids opening/requesting a
            # GPIO line or writing relay safe-off merely to validate config.
            if getattr(args, "as_json", False):
                print(json.dumps(payload, sort_keys=True))
            else:
                print("[OK] code=ENVIRONMENT_DAEMON_CONFIG_OK enabled=true hardware_toggled=false physical_evidence=false")
            return 0
        from .environment.journal import EnvironmentEventJournal
        with EnvironmentEventJournal() as journal:
            daemon = EnvironmentDaemon.from_config(env, event_sink=journal)
            daemon.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except EnvironmentDaemonError as exc:
        return _environment_error(str(exc.code), _environment_public_message(exc), getattr(args, "as_json", False))
    except Exception as exc:
        return _environment_error("ENV_DAEMON_FAILED", type(exc).__name__, getattr(args, "as_json", False))

def _environment_client_from_args(args: argparse.Namespace):
    socket_path = args.socket
    if socket_path is None:
        effective = load_config()
        socket_path = Path(effective.config.extensions.environment.socket_path)
    return _make_environment_client(socket_path)


def _make_environment_client(socket_path: Path | str):
    from .environment import EnvironmentClient

    return EnvironmentClient(socket_path)


def _call_environment_command(client: object, args: argparse.Namespace) -> Mapping[str, object]:
    command = args.env_command
    if command == "status":
        return client.status()  # type: ignore[attr-defined]
    if command == "health":
        return client.health()  # type: ignore[attr-defined]
    if command in {"temperature", "humidity", "read"}:
        return client.read_sensor()  # type: ignore[attr-defined]
    if command == "probe":
        call = getattr(client, "call")
        return call("probe.run").result  # type: ignore[no-any-return]
    if command == "fan":
        return client.fan_set(args.fan_command)  # type: ignore[attr-defined]
    if command == "mode":
        if args.mode_command != "set":
            raise ValueError("unsupported mode command")
        return client.mode_set(args.mode)  # type: ignore[attr-defined]
    if command == "policy":
        if args.policy_command == "show":
            return client.policy_get()  # type: ignore[attr-defined]
        if args.policy_command == "set":
            update = {
                "expected_generation": args.expected_generation,
                "mode": args.mode,
                "start_c": args.start_c,
                "stop_c": args.stop_c,
                "minimum_on_seconds": args.minimum_on_seconds,
                "minimum_off_seconds": args.minimum_off_seconds,
            }
            selected = {key: value for key, value in update.items() if value is not None}
            if not selected:
                raise ValueError("policy set requires at least one field")
            return client.policy_update(**selected)  # type: ignore[attr-defined]
    if command == "simulate":
        return _call_environment_simulation_command(client, args)
    raise ValueError(f"unsupported env command: {command}")


def _call_environment_simulation_command(client: object, args: argparse.Namespace) -> Mapping[str, object]:
    command = args.simulate_command
    if command == "status":
        return client.simulation_status()  # type: ignore[attr-defined]
    if command == "reset":
        return client.simulation_reset()  # type: ignore[attr-defined]
    if command == "sensor":
        sensor_command = args.simulate_sensor_command
        if sensor_command in {"set", "recover"}:
            return client.simulation_sensor_set(  # type: ignore[attr-defined]
                temperature_c=args.temperature_c,
                relative_humidity_pct=args.humidity_pct,
            )
        if sensor_command == "unavailable":
            return client.simulation_sensor_fault("unavailable")  # type: ignore[attr-defined]
        if sensor_command == "crc-error":
            return client.simulation_sensor_fault("crc_error")  # type: ignore[attr-defined]
        if sensor_command == "stale":
            return client.simulation_sensor_fault("stale", age_seconds=args.age_seconds)  # type: ignore[attr-defined]
        if sensor_command == "reset":
            return client.simulation_sensor_reset()  # type: ignore[attr-defined]
    if command == "fan":
        fan_command = args.simulate_fan_command
        if fan_command == "show":
            return client.simulation_status()  # type: ignore[attr-defined]
        if fan_command == "behavior":
            return client.simulation_actuator_behavior_set(args.behavior)  # type: ignore[attr-defined]
        if fan_command == "unavailable":
            return client.simulation_actuator_behavior_set("unavailable")  # type: ignore[attr-defined]
        if fan_command == "fail-next-write":
            return client.simulation_actuator_behavior_set("fail_next_write")  # type: ignore[attr-defined]
        if fan_command == "reset":
            return client.simulation_actuator_reset()  # type: ignore[attr-defined]
    raise ValueError("unsupported simulation command")


def _print_environment_payload(args: argparse.Namespace, payload: Mapping[str, object]) -> None:
    command = args.env_command
    if command == "status":
        state = _payload_state(payload)
        print(f"Environment: {payload.get('environment', 'UNKNOWN')}")
        print(f"Mode: {state.get('mode', 'unknown')}")
        print(f"Fan power: {state.get('fan_power', 'unknown')}")
        print(f"Sensor: {state.get('sensor_quality', 'unknown')}")
        print(f"Control temperature: {_format_value(state.get('control_temperature_c'), 'C')}")
        print(f"Last transition: {state.get('last_transition_reason', 'unknown')}")
        capabilities = payload.get("capabilities")
        if isinstance(capabilities, Mapping):
            print(
                "Capabilities: "
                f"power_control={capabilities.get('power_control')}, "
                f"software_speed_control={capabilities.get('software_speed_control')}, "
                f"fan_motion_observed={capabilities.get('fan_motion_observed')}"
            )
        identity = payload.get("actuator_runtime_identity")
        if isinstance(identity, Mapping):
            mapping = identity.get("status", "UNKNOWN")
            if mapping == "RESOLVED":
                print(
                    "Actuator GPIO: "
                    f"BCM{identity.get('logical_bcm')} -> "
                    f"{identity.get('chip_path')}:{identity.get('line_offset')} "
                    f"({identity.get('line_name')})"
                )
            else:
                print(f"Actuator GPIO: {mapping} ({identity.get('code', identity.get('backend', 'unknown'))})")
        print(f"Physical Pi evidence: {payload.get('physical_evidence', False)}")
        return
    if command == "health":
        print(f"Overall: {payload.get('overall', 'UNKNOWN')}")
        print(f"Sensor: {payload.get('sensor', 'unknown')}")
        print(f"Actuator: {payload.get('actuator', 'unknown')}")
        identity = payload.get("actuator_runtime_identity")
        if isinstance(identity, Mapping):
            print(f"Actuator mapping: {identity.get('status', 'UNKNOWN')}")
        print(f"Controller: {payload.get('controller', 'unknown')}")
        print(f"Physical Pi evidence: {payload.get('physical_evidence', False)}")
        return
    if command in {"temperature", "humidity", "read"}:
        reading = payload.get("reading")
        if not isinstance(reading, Mapping):
            print("Sensor reading: unavailable")
            return
        if command in {"temperature", "read"}:
            print(f"Temperature: {_format_value(reading.get('temperature_c'), 'C')}")
        if command in {"humidity", "read"}:
            print(f"Humidity: {_format_value(reading.get('relative_humidity_pct'), '%RH')}")
        print(f"Sensor quality: {reading.get('quality', reading.get('error_code', 'unknown'))}")
        print(f"Physical Pi evidence: {payload.get('physical_evidence', False)}")
        return
    if command == "probe":
        print(f"Probe: {payload.get('probe', 'unknown')}")
        print(f"Destructive: {payload.get('destructive', False)}")
        print(f"Hardware toggled: {payload.get('hardware_toggled', False)}")
        print(f"Status: {payload.get('status', 'unknown')}")
        return
    if command == "simulate":
        _print_environment_simulation_payload(payload)
        return
    if command in {"fan", "mode"} or command == "policy" and getattr(args, "policy_command", None) == "set":
        state = _payload_state(payload)
        policy = payload.get("policy") if isinstance(payload.get("policy"), Mapping) else state.get("policy")
        print(f"Mode: {state.get('mode', 'unknown')}")
        print(f"Fan power: {state.get('fan_power', 'unknown')}")
        print(f"Last transition: {state.get('last_transition_reason', 'unknown')}")
        if isinstance(policy, Mapping):
            print(f"Policy generation: {policy.get('generation', 'unknown')}")
            print(f"Start threshold: {_format_value(policy.get('start_c'), 'C')}")
            print(f"Stop threshold: {_format_value(policy.get('stop_c'), 'C')}")
        print(f"Physical Pi evidence: {payload.get('physical_evidence', False)}")
        return
    if command == "policy":
        policy = payload.get("policy")
        bounds = payload.get("bounds")
        if isinstance(policy, Mapping):
            print(f"Mode: {policy.get('mode', 'unknown')}")
            print(f"Policy generation: {policy.get('generation', 'unknown')}")
            print(f"Start threshold: {_format_value(policy.get('start_c'), 'C')}")
            print(f"Stop threshold: {_format_value(policy.get('stop_c'), 'C')}")
            print(f"Minimum on: {_format_value(policy.get('minimum_on_seconds'), 's')}")
            print(f"Minimum off: {_format_value(policy.get('minimum_off_seconds'), 's')}")
        if isinstance(bounds, Mapping):
            print(
                "Bounds: "
                f"temperature={bounds.get('temperature_min_c')}..{bounds.get('temperature_max_c')} C, "
                f"hysteresis={bounds.get('minimum_hysteresis_c')}..{bounds.get('maximum_hysteresis_c')} C"
            )
        return
    print(json.dumps(payload, sort_keys=True))



def _environment_watch_signature(payload: Mapping[str, object]) -> tuple[object, ...]:
    state = _payload_state(payload)
    reading = payload.get("reading")
    if not isinstance(reading, Mapping):
        reading = state.get("last_reading")
    reading_map = reading if isinstance(reading, Mapping) else {}
    provenance = payload.get("provenance") if isinstance(payload.get("provenance"), Mapping) else {}
    polling = payload.get("polling") if isinstance(payload.get("polling"), Mapping) else {}
    policy = state.get("policy") if isinstance(state.get("policy"), Mapping) else {}
    return (
        state.get("mode"), state.get("fan_power"), state.get("sensor_quality"),
        state.get("last_transition_reason"), policy.get("generation"),
        reading_map.get("quality"), provenance.get("sensor_backend"),
        provenance.get("actuator_backend"), polling.get("last_poll_error_code"),
        provenance.get("release_commit"), provenance.get("configuration_sha256"),
        (payload.get("actuator_commands") or {}).get("relay_commanded") if isinstance(payload.get("actuator_commands"), Mapping) else None,
        (payload.get("actuator_commands") or {}).get("last_write_result") if isinstance(payload.get("actuator_commands"), Mapping) else None,
        (payload.get("health") or {}).get("actuator") if isinstance(payload.get("health"), Mapping) else None,
    )

def _print_environment_watch_row(payload: Mapping[str, object]) -> None:
    state = _payload_state(payload)
    reading = payload.get("reading")
    if not isinstance(reading, Mapping):
        reading = state.get("last_reading")
    reading_map = reading if isinstance(reading, Mapping) else {}
    provenance = payload.get("provenance") if isinstance(payload.get("provenance"), Mapping) else {}
    policy = state.get("policy") if isinstance(state.get("policy"), Mapping) else {}
    print(
        f"{time.strftime('%H:%M:%S')}  "
        f"{_format_value(reading_map.get('temperature_c'), 'C')}  "
        f"{_format_value(reading_map.get('relative_humidity_pct'), '%RH')}  "
        f"sensor={reading_map.get('source_backend', provenance.get('sensor_backend', 'unknown'))}  "
        f"actuator={provenance.get('actuator_backend', 'unknown')}  "
        f"mode={state.get('mode', 'unknown')}  "
        f"controller_desired={state.get('fan_power', 'unknown')}  "
        f"relay_commanded={(payload.get('actuator_commands') or {}).get('relay_commanded', 'unreported') if isinstance(payload.get('actuator_commands'), Mapping) else 'unreported'}  "
        f"fan_motion=unobserved  "
        f"gpio={(payload.get('actuator_runtime_identity') or {}).get('line_name', 'none') if isinstance(payload.get('actuator_runtime_identity'), Mapping) else 'none'}  "
        f"actuator_errors={(payload.get('actuator_commands') or {}).get('actuator_write_errors', 'unreported') if isinstance(payload.get('actuator_commands'), Mapping) else 'unreported'}  "
        f"quality={reading_map.get('quality', state.get('sensor_quality', 'unknown'))}  "
        f"reason={state.get('last_transition_reason', 'unknown')}  "
        f"policy_generation={policy.get('generation', 'unknown')}  "
        f"polls={(payload.get('polling') or {}).get('poll_count', 'unknown') if isinstance(payload.get('polling'), Mapping) else 'unknown'}  "
        f"poll_errors={(payload.get('polling') or {}).get('poll_error_count', 'unknown') if isinstance(payload.get('polling'), Mapping) else 'unknown'}  "
        f"physical_evidence={payload.get('physical_evidence', False)}",
        flush=True,
    )


def _print_environment_simulation_payload(payload: Mapping[str, object]) -> None:
    simulation = payload.get("simulation") if isinstance(payload.get("simulation"), Mapping) else {}
    sensor = simulation.get("sensor") if isinstance(simulation.get("sensor"), Mapping) else {}
    actuator = simulation.get("actuator") if isinstance(simulation.get("actuator"), Mapping) else {}
    print(f"Simulation active: {simulation.get('active', False)}")
    print(f"Runtime control enabled: {simulation.get('runtime_control_enabled', False)}")
    print(f"Sensor simulated: {simulation.get('sensor_is_simulated', False)}")
    print(f"Actuator simulated: {simulation.get('actuator_is_simulated', False)}")
    print(f"Evidence mode: {simulation.get('evidence_mode', 'unknown')}")
    print(f"Generation: {simulation.get('simulation_generation', 'unknown')}")
    if simulation.get("sensor_is_simulated", False):
        print(f"Sensor: simulated temp={_format_value(sensor.get('temperature_c'), 'C')} humidity={_format_value(sensor.get('relative_humidity_pct'), '%RH')} fault={sensor.get('fault')}")
    else:
        print("Sensor: physical/non-simulated; live values are reported by `gonken-agent env read` or `env watch`")
    print(f"Fan: behavior={actuator.get('behavior', 'unknown')} commanded={actuator.get('commanded_power', 'unknown')} modeled={actuator.get('modeled_power', 'unknown')}")
    print(f"Physical Pi evidence: {payload.get('physical_evidence', False)}")


def _payload_state(payload: Mapping[str, object]) -> Mapping[str, object]:
    state = payload.get("state")
    return state if isinstance(state, Mapping) else {}


def _format_value(value: object, suffix: str) -> str:
    if isinstance(value, bool) or value is None:
        return "unavailable"
    if isinstance(value, (int, float)):
        return f"{float(value):.1f} {suffix}" if suffix == "C" else f"{float(value):.1f} {suffix}"
    return str(value)


def _environment_error(code: str, message: str, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"status": "FAILED", "code": code, "message": message}, sort_keys=True), file=sys.stderr)
    else:
        print(f"Environment command failed: {code}: {message}", file=sys.stderr)
    return EXIT_FAILED


def _environment_public_message(exc: BaseException) -> str:
    text = str(exc)
    if ": " in text:
        return text.split(": ", 1)[1]
    return text or type(exc).__name__


def entrypoint() -> None:
    """Console-script adapter."""

    raise SystemExit(main())


def _print_effective_config(
    values: dict[str, object], sources: Mapping[str, str], prefix: str = ""
) -> None:
    for key, value in values.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _print_effective_config(value, sources, dotted)
        else:
            print(f"{dotted} = {value!r} [{sources[dotted]}]")
