from __future__ import annotations
import contextlib
import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from gonken_agent import evidence, operations
from gonken_agent.cli import _build_parser

class EvidenceTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.out=self.root/'evidence.tar.bz2'
        self.data={'platform.json':{'status':'READY','board':'Raspberry Pi 5','gpio':23},
                   'health.json':{'status':'DEGRADED','code':'AUDIO_CAPTURE_FAILED'}}

    def create(self):
        return evidence.write_bundle(self.out,self.data,bundle_kind='support')

    def mutate_archive(self, fn):
        with tarfile.open(self.out,'r:bz2') as archive:
            rows=[(i,archive.extractfile(i).read()) for i in archive]
        rows=fn(rows)
        with tarfile.open(self.out,'w:bz2') as archive:
            for info,raw in rows:
                info.size=len(raw)
                archive.addfile(info,io.BytesIO(raw) if info.isfile() else None)

    def test_actual_tar_and_bidirectional_index(self):
        result=self.create()
        self.assertTrue(result['verified']); self.assertEqual(result['archive_format'],'tar.bz2')
        self.assertEqual(self.out.read_bytes()[:3],b'BZh')
        index=evidence.verify_bundle(self.out)
        self.assertEqual(evidence.read_json_members(self.out),self.data)
        self.assertEqual({r['path'] for r in index['members']},set(self.data))
        self.assertFalse(index['physical_acceptance_claimed'])
        self.assertEqual(self.out.stat().st_mode&0o777,0o600)
        with tarfile.open(self.out) as a:
            for i in a:
                self.assertTrue(i.isfile()); self.assertEqual(i.mode,0o600)

    def test_existing_output_never_overwritten(self):
        self.create(); old=self.out.read_bytes()
        with self.assertRaises(ValueError): self.create()
        self.assertEqual(old,self.out.read_bytes())

    def test_symlink_output_refused(self):
        self.out.symlink_to(self.root/'other')
        with self.assertRaises(ValueError): self.create()
        self.assertFalse((self.root/'other').exists())

    def test_legacy_zip_destination_refused(self):
        with self.assertRaises(ValueError): evidence.write_bundle(self.root/'out.zip',self.data,bundle_kind='support')
        with self.assertRaises(ValueError): evidence.resolve_output_path(prefix='gonken',output=self.root/'out.zip')

    def test_duplicate_member_rejected(self):
        self.create(); self.mutate_archive(lambda rows: rows+[rows[0]])
        with self.assertRaises(ValueError): evidence.verify_bundle(self.out)

    def test_unknown_unindexed_member_rejected(self):
        self.create(); self.mutate_archive(lambda rows: rows+[(tarfile.TarInfo('extra.json'),b'{}')])
        with self.assertRaises(ValueError): evidence.read_json_members(self.out)

    def test_missing_member_rejected(self):
        self.create(); self.mutate_archive(lambda rows: [r for r in rows if r[0].name!='health.json'])
        with self.assertRaises(ValueError): evidence.verify_bundle(self.out)

    def test_digest_mismatch_rejected(self):
        self.create(); self.mutate_archive(lambda rows:[(i,b'{}' if i.name=='health.json' else raw) for i,raw in rows])
        with self.assertRaises(ValueError): evidence.verify_bundle(self.out)

    def test_missing_or_duplicate_index_rejected(self):
        self.create(); self.mutate_archive(lambda rows:[r for r in rows if r[0].name!='evidence_index.json'])
        with self.assertRaises(ValueError): evidence.verify_bundle(self.out)

    def test_path_traversal_and_links_refused_without_extraction(self):
        for name,kind in (('../secret.json',tarfile.REGTYPE), ('link.json',tarfile.SYMTYPE),
                          ('hard.json',tarfile.LNKTYPE), ('/absolute.json',tarfile.REGTYPE)):
            with self.subTest(name=name):
                info=tarfile.TarInfo(name); info.type=kind; info.linkname='/tmp/private'
                with tarfile.open(self.out,'w:bz2') as a:
                    raw=b'{}'; info.size=len(raw) if info.isfile() else 0
                    a.addfile(info,io.BytesIO(raw) if info.isfile() else None)
                with self.assertRaises(ValueError): evidence.verify_bundle(self.out)
        self.assertFalse((self.root/'secret.json').exists())

    def test_archive_size_limits(self):
        self.data={'big.json':{'value':'x'*(evidence.MAX_MEMBER_BYTES+1)}}
        with self.assertRaises(ValueError): self.create()
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.root.iterdir()),[])

    def test_fail_during_compression_preserves_previous_state(self):
        with mock.patch.object(evidence.tarfile,'open',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.create()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_failed_verification_not_published(self):
        with mock.patch.object(evidence,'verify_bundle',side_effect=ValueError('bad member')):
            with self.assertRaises(ValueError): self.create()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_publish_race_does_not_replace_other_writer(self):
        def race(_source,target,**_kw):
            Path(target).write_bytes(b'other writer')
            raise FileExistsError()
        with mock.patch.object(evidence.os,'link',side_effect=race):
            with self.assertRaises(FileExistsError): self.create()
        self.assertEqual(self.out.read_bytes(),b'other writer')
        self.assertEqual(len(list(self.root.iterdir())),1)

    def test_nonfinite_and_duplicate_json_refused(self):
        self.create()
        self.mutate_archive(lambda rows:[(i,b'{"x":1,"x":2}' if i.name=='health.json' else raw) for i,raw in rows])
        with self.assertRaises(ValueError): evidence.verify_bundle(self.out)

    def test_index_cannot_grant_physical_acceptance(self):
        self.create()
        def mutate(rows):
            out=[]
            for i,raw in rows:
                if i.name=='evidence_index.json':
                    v=json.loads(raw); v['physical_acceptance_claimed']=True; raw=json.dumps(v).encode()
                out.append((i,raw))
            return out
        self.mutate_archive(mutate)
        with self.assertRaises(ValueError): evidence.verify_bundle(self.out)

    def test_new_output_dir_must_preexist(self):
        missing=self.root/'missing'
        with self.assertRaises(ValueError): evidence.resolve_output_path(prefix='gonken',output_dir=missing)
        self.assertFalse(missing.exists())

    def test_default_user_home_and_sudo_home(self):
        with mock.patch.object(evidence,'invoking_user_identity',return_value=(1000,1000,self.root)):
            p=evidence.resolve_output_path(prefix='gonken')
            self.assertEqual(p.parent,self.root); self.assertTrue(p.name.endswith('.tar.bz2'))
        with mock.patch.object(evidence,'invoking_user_identity',return_value=None), \
             mock.patch.object(evidence.os,'geteuid',return_value=1000), mock.patch.object(Path,'home',return_value=self.root):
            self.assertEqual(evidence.resolve_output_path(prefix='gonken').parent,self.root)

    def test_no_unvalidated_sudo_chown(self):
        self.out.write_bytes(b'data')
        with mock.patch.object(evidence,'invoking_user_identity',return_value=None),mock.patch.object(evidence.os,'chown') as chown:
            self.assertFalse(evidence.return_ownership_to_invoking_user(self.out)); chown.assert_not_called()

    def test_filename_prefix_cannot_traverse(self):
        with self.assertRaises(ValueError): evidence.resolve_output_path(prefix='../bad',output_dir=self.root)

    def test_cli_output_options_and_human_summary(self):
        parser=_build_parser()
        for extra in ([],['--json']):
            args=parser.parse_args(['support','--no-site','--output-dir',str(self.root),*extra])
            with mock.patch('gonken_agent.support.create_bundle',return_value={'status':'CREATED','verified':True}) as create, \
                 mock.patch.object(operations,'doctor',return_value={}), \
                 mock.patch('gonken_agent.evidence.return_ownership_to_invoking_user'), \
                 contextlib.redirect_stdout(io.StringIO()) as buf:
                self.assertEqual(operations.execute(args),0)
            self.assertTrue(str(create.call_args.args[0]).endswith('.tar.bz2'))
            if extra: self.assertTrue(json.loads(buf.getvalue())['verified'])
            else:
                self.assertIn('[EVIDENCE] bundle:',buf.getvalue())
                self.assertFalse(buf.getvalue().startswith('{'))

if __name__=='__main__': unittest.main()
