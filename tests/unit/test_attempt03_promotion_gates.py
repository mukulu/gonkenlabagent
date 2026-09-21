from __future__ import annotations
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from scripts import release_readiness as readiness, current_state, archive_qualifier

ROOT=Path(__file__).resolve().parents[2]

class CurrentPromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.docs=self.root/'docs/development'; self.docs.mkdir(parents=True)
        self.data=json.loads((ROOT/'docs/development/CURRENT_GATES.json').read_text())
        self.plan=json.loads((ROOT/'docs/development/ATTEMPT03_PLAN.json').read_text())
        (self.root/'verified.md').write_text('synthetic evidence fixture, not physical acceptance')
        for row in self.data['slots']: row['evidence']=['verified.md']
        self.save()

    def save(self):
        (self.docs/'CURRENT_GATES.json').write_text(json.dumps(self.data))
        (self.docs/'ATTEMPT03_PLAN.json').write_text(json.dumps(self.plan))

    def report(self, *, dirty=False, allow_dirty=False, shadow=None):
        with mock.patch.object(readiness,'ROOT',self.root), mock.patch.object(readiness,'DOCS',self.docs), \
             mock.patch.object(readiness,'scan_secrets',return_value=[]), \
             mock.patch.object(readiness,'target_shadow_results',return_value=shadow or [{'id':'fake','status':'PASS'}]), \
             mock.patch.object(readiness,'git_state',return_value={'branch':'dev-unstable/test','commit':'a'*40,'dirty':dirty}):
            return readiness.build_report(allow_dirty=allow_dirty)

    def close_core_fixture(self):
        required={r['id'] for r in self.plan['slots'] if r['required_before_core_candidate']}
        for row in self.data['slots']:
            if row['id'] in required: row['status']='HOST_VERIFIED'
        self.save()

    def test_old_milestones_are_not_current_authority(self):
        (self.docs/'MILESTONES.json').write_text('not valid JSON: must not be read for promotion')
        report=self.report()
        self.assertEqual(report['status'],'NOT_READY'); self.assertEqual(report['validation_status'],'PASS')
        self.assertTrue(report['current_gates_remaining'])

    def test_allow_dirty_never_bypasses_unfinished_gates(self):
        report=self.report(dirty=True,allow_dirty=True)
        self.assertEqual(report['validation_status'],'PASS'); self.assertEqual(report['status'],'NOT_READY')

    def test_missing_registry_fails_closed(self):
        (self.docs/'CURRENT_GATES.json').unlink()
        self.assertEqual(self.report()['validation_status'],'FAIL')

    def test_missing_plan_fails_closed(self):
        (self.docs/'ATTEMPT03_PLAN.json').unlink()
        self.assertEqual(self.report()['validation_status'],'FAIL')

    def test_removed_slot_fails_coverage(self):
        self.data['slots'].pop(); self.save()
        self.assertIn('BLUEPRINT_COVERAGE_MISMATCH',self.report()['state_errors'])

    def test_unknown_slot_fails_coverage(self):
        self.data['slots'].append(dict(self.data['slots'][0],id='46.99.1')); self.save()
        self.assertIn('BLUEPRINT_COVERAGE_MISMATCH',self.report()['state_errors'])

    def test_requirement_cannot_be_made_optional(self):
        self.plan['slots'][0]['required_before_core_candidate']=False; self.save()
        self.assertIn('BLUEPRINT_REQUIREMENT_CLASS',self.report()['state_errors'])

    def test_title_drift_fails(self):
        self.data['slots'][0]['title']='different scope'; self.save()
        self.assertEqual(self.report()['validation_status'],'FAIL')

    def test_declared_completion_without_evidence_fails(self):
        self.data['slots'][0].update(status='HOST_VERIFIED',evidence=[]); self.save()
        self.assertEqual(self.report()['validation_status'],'FAIL')

    def test_symlink_evidence_rejected(self):
        (self.root/'alias.md').symlink_to(self.root/'verified.md')
        self.data['slots'][0]['evidence']=['alias.md']; self.save()
        self.assertEqual(self.report()['validation_status'],'FAIL')

    def test_complete_core_does_not_claim_physical_or_require_optional_display(self):
        self.close_core_fixture()
        report=self.report()
        self.assertEqual(report['status'],readiness.READY_STATUS)
        self.assertFalse(report['physical_acceptance_claimed']); self.assertTrue(report['target_gates_remaining'])

    def test_bad_shadow_blocks_even_complete_core(self):
        self.close_core_fixture()
        report=self.report(shadow=[{'id':'fake','status':'FAIL'}])
        self.assertEqual(report['validation_status'],'FAIL'); self.assertEqual(report['status'],'NOT_READY')

    def test_dirty_source_not_promoted_without_explicit_override(self):
        self.close_core_fixture()
        self.assertEqual(self.report(dirty=True)['status'],'NOT_READY')

    def test_validate_exit_distinct_from_promotion(self):
        report=self.report()
        with mock.patch.object(readiness,'build_report',return_value=report),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(readiness.main(['--validate','--json']),0)
            self.assertEqual(readiness.main(['--check','--json']),1)

    def test_validation_failure_has_nonzero_exit(self):
        report=self.report(); report['validation_status']='FAIL'
        with mock.patch.object(readiness,'build_report',return_value=report),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(readiness.main(['--validate']),1)

    def test_cli_gates_are_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as raised:
            readiness.main(['--check','--validate'])
        self.assertEqual(raised.exception.code,2)

class ArchivePurposeTests(unittest.TestCase):
    def test_development_uses_validation_without_candidate_label(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'source.tar.bz2'; p.write_bytes(b'synthetic')
            def extract(_archive,dest): (dest/'repo').mkdir()
            def success(command,cwd,**kw): return {'status':'PASS','exit':0,'command':command,'stdout':''}
            with mock.patch.object(archive_qualifier,'inspect_tar',return_value={'status':'PASS','root':'repo'}), \
                 mock.patch.object(archive_qualifier,'extract_tar_preserving_permissions',side_effect=extract), \
                 mock.patch.object(archive_qualifier,'_git_text',return_value='a'*40), \
                 mock.patch.object(archive_qualifier,'_run',side_effect=success) as run:
                report=archive_qualifier.qualify_archive(p,purpose='development',run_t0=False,expected_commit='a'*40)
                self.assertEqual(report['status'],'PASS'); self.assertFalse(report['raspberry_pi_candidate'])
                self.assertTrue(any('--validate' in c.args[0] for c in run.call_args_list))
                target=archive_qualifier.qualify_archive(p,purpose='target-candidate',run_t0=False,expected_commit='a'*40)
                self.assertEqual(target['status'],'FAIL'); self.assertFalse(target['raspberry_pi_candidate'])
                unpinned=archive_qualifier.qualify_archive(p,purpose='target-candidate')
                self.assertEqual(unpinned['status'],'FAIL')

    def test_invalid_purpose_rejected(self):
        with self.assertRaises(ValueError): archive_qualifier.qualify_archive(Path('never-read'),purpose='stable-anyway')

if __name__=='__main__': unittest.main()
