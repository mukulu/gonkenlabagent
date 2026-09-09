"""Render the complete status ledger; --check is a non-mutating CI gate."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    docs = ROOT / 'docs/development'
    data = json.loads((docs / 'MILESTONES.json').read_text())
    rows = data['milestones']
    expected = re.findall(r'^#### (M\d+\.\d+) ', (docs / 'MASTER_BLUEPRINT.md').read_text(), re.M)
    if [r['id'] for r in rows] != expected:
        raise SystemExit('Milestone ledger must cover blueprint items exactly once in order')
    rendered = '\nCheckpoint scope: **' + data['checkpoint_scope'] + '**\n\n'
    rendered += '| Item | Software | Target acceptance | Evidence / remaining work |\n|---|---|---|---|\n'
    for row in rows:
        if row['software'] not in {'pending', 'partial', 'host-verified', 'blocked'}:
            raise SystemExit('Unknown software state')
        if row['software'] == 'host-verified' and not row['evidence']:
            raise SystemExit('Verified items require evidence')
        cells = [row['id'] + ' — ' + row['title'], row['software'], row['target'], row['evidence'] + ' ' + row['remaining']]
        if any('\n' in c or '|' in c for c in cells):
            raise SystemExit('Unsafe table cell')
        rendered += '| ' + ' | '.join(cells) + ' |\n'
    path = docs / 'IMPLEMENTATION_STATUS.md'
    old = path.read_text()
    new = re.sub(r'(?s)(<!-- MILESTONES -->).*?(<!-- /MILESTONES -->)', lambda m: m[1] + rendered + m[2], old)
    if args.check:
        if new != old:
            raise SystemExit('Status drift: run python scripts/milestone_status.py')
    else:
        path.write_text(new)


if __name__ == '__main__':
    main()
