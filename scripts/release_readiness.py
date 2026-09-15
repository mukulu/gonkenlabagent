"""Report whether the repository can move to Raspberry Pi acceptance testing."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "development"
REQUIRED_HOST_VERIFIED = {
    "M2.1", "M2.2", "M2.3", "M2.4",
    "M3.1", "M3.2", "M3.3", "M3.4", "M3.5", "M3.6",
    "M4.1", "M4.2", "M4.3",
    "M5.1", "M5.2",
    "M6.1", "M6.2",
    # M7.1/M7.2/M7.5 intentionally remain evaluation gates because they require
    # the real lab corpus/model/benchmark campaign.  Core privacy/dashboard
    # software must nevertheless be host-verified before target handoff.
    "M7.3", "M7.4",
    "M8.1", "M8.2", "M8.3",
    "M9.2", "M9.3", "M9.4", "M9.5",
    "M10.1", "M10.2", "M10.3", "M10.4", "M10.5", "M10.6",
    "M10.8", "M10.9", "M10.10", "M10.11", "M10.12", "M10.13", "M10.14", "M10.15",
    "M10.16", "M10.17", "M10.18", "M10.19", "M10.20", "M10.21", "M10.22", "M10.23", "M10.25", "M10.26",
}
TARGET_CAMPAIGN_ITEMS = {
    "M3.1", "M3.2", "M3.3", "M3.4", "M3.5", "M3.6",
    "M4.1", "M4.2", "M4.3",
    "M5.1", "M5.2",
    "M6.1", "M6.2",
    "M7.1", "M7.2", "M7.3", "M7.4", "M7.5",
    "M8.1", "M8.2", "M8.3", "M9.1", "M9.2", "M9.3",
    "M10.7", "M10.24",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
}
TEXT_EXTENSIONS = {
    ".py", ".sh", ".toml", ".md", ".json", ".cfg", ".ini", ".service", ".conf", ".txt"
}
SCAN_ROOTS = ("src", "scripts", "packaging", "requirements", "tests", "config", "README.md", "pyproject.toml", "AGENTS.md")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--check", action="store_true", help="exit nonzero unless ready for target acceptance")
    parser.add_argument("--allow-dirty", action="store_true", help="ignore only uncommitted worktree changes")
    args = parser.parse_args()
    report = build_report()
    if args.allow_dirty and report["git"]["dirty"] and not report["missing_milestones"] and not report["not_host_verified"] and not report["secret_findings"]:
        report = {**report, "status": "READY_FOR_TARGET_ACCEPTANCE"}
    if args.as_json:
        print(json.dumps(report, sort_keys=True, indent=2))
    else:
        print(f"Status: {report['status']}")
        print(f"Branch: {report['git']['branch']}")
        print(f"Commit: {report['git']['commit']}")
        print(f"Dirty tree: {report['git']['dirty']}")
        print(f"Host verified required items: {len(report['host_verified'])}/{len(REQUIRED_HOST_VERIFIED)}")
        print(f"Target gates remaining: {len(report['target_gates_remaining'])}")
        for gate in report["target_gates_remaining"][:12]:
            print(f"- {gate['id']}: {gate['title']}")
    if args.check and report["status"] != "READY_FOR_TARGET_ACCEPTANCE":
        return 1
    return 0


def build_report() -> dict[str, object]:
    milestones = json.loads((DOCS / "MILESTONES.json").read_text(encoding="utf-8"))
    rows = milestones["milestones"]
    by_id = {row["id"]: row for row in rows}
    missing = sorted(REQUIRED_HOST_VERIFIED - set(by_id))
    not_host_verified = sorted(
        item for item in REQUIRED_HOST_VERIFIED
        if item in by_id and by_id[item]["software"] != "host-verified"
    )
    target_gates = [
        {
            "id": row["id"],
            "title": row["title"],
            "target": row["target"],
            "remaining": row["remaining"],
        }
        for row in rows
        if row["id"] in TARGET_CAMPAIGN_ITEMS and row["target"] == "not-run"
    ]
    secrets = scan_secrets()
    git = git_state()
    status = "READY_FOR_TARGET_ACCEPTANCE"
    if missing or not_host_verified or secrets or git["dirty"]:
        status = "NOT_READY"
    return {
        "schema": 1,
        "status": status,
        "checkpoint_scope": milestones["checkpoint_scope"],
        "git": git,
        "host_verified": sorted(REQUIRED_HOST_VERIFIED - set(not_host_verified) - set(missing)),
        "missing_milestones": missing,
        "not_host_verified": not_host_verified,
        "secret_findings": secrets,
        "target_gates_remaining": target_gates,
        "readiness_scope": "host/software complete enough to begin the recorded Raspberry Pi target campaign; no target gate is implied PASS",
        "physical_acceptance_claimed": False,
        "next_action": (
            "Verify the delivered comprehensive-closure checkpoint and install that exact clean commit with ./bootstrap.sh --local-checkpoint; "
            "allow a governed I2C_REBOOT_REQUIRED stop to reboot and resume the same installer, but require INSTALLATION_COMPLETE before integrated hardware actuation; "
            "then execute docs/RASPBERRY_PI_ACCEPTANCE_RUN.md through simulation, physical fan, real SHT31, full-real voice/fault/reboot/update/rollback stages; "
            "collect the support ZIP plus M10.7/M10.24 private evidence and do not mark any remaining physical gate PASS without observed target evidence."
        ),
    }


def git_state() -> dict[str, object]:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    return {
        "branch": run("branch", "--show-current"),
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(run("status", "--porcelain")),
    }


def scan_secrets() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for item in SCAN_ROOTS:
        path = ROOT / item
        candidates = [path] if path.is_file() else path.rglob("*")
        for candidate in candidates:
            if not candidate.is_file() or candidate.is_symlink() or candidate.suffix not in TEXT_EXTENSIONS:
                continue
            relative = candidate.relative_to(ROOT).as_posix()
            text = candidate.read_text(encoding="utf-8", errors="replace")
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    findings.append({"file": relative, "pattern": name})
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
