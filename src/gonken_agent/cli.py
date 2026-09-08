"""Dependency-light command-line boundary."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from . import IDENTITY, __version__
from .compat import CompatibilityError, run_legacy_source


EXIT_FAILED = 1
EXIT_UNSUPPORTED = 3


def _status() -> dict[str, object]:
    return {
        "product": IDENTITY.product_name,
        "package": IDENTITY.package_name,
        "version": __version__,
        "package_foundation": "complete",
        "core_runtime_ready": False,
        "redistribution_approved": False,
        "redistribution_policy": "prohibited",
        "extensions": {
            "wake_word": "disabled",
            "voice_power": "disabled",
            "lan_dashboard": "disabled",
            "bluetooth": "disabled",
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the CLI and return a stable process exit code."""

    parser = _build_parser()
    args = parser.parse_args(argv)

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
            print("Core runtime: not yet implemented through the package boundary")
            print("Redistribution: prohibited; no project license is granted")
            print("Extensions: disabled")
        return 0
    if args.command == "run":
        if not args.legacy_source:
            print(
                "The packaged core runtime is not implemented yet. "
                "Use --legacy-source only for migration testing.",
                file=sys.stderr,
            )
            return EXIT_UNSUPPORTED
        try:
            return run_legacy_source()
        except CompatibilityError as exc:
            print(f"Cannot start compatibility runtime: {exc}", file=sys.stderr)
            return EXIT_FAILED

    parser.error(f"unsupported command: {args.command}")
    return EXIT_UNSUPPORTED


def entrypoint() -> None:
    """Console-script adapter."""

    raise SystemExit(main())
