"""Dependency-light command-line boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
    wake_phrase = "Hey Gonken"
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
