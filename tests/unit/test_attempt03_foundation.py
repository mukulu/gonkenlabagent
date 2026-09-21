from __future__ import annotations
import copy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
state=load('current_state'); archive=load('archive_qualifier')
class CurrentStateTests(unittest.TestCase):
 def setUp(self): self.data=json.loads((ROOT/'docs/development/CURRENT_GATES.json').read_text())
 def test_current_registry_valid(self): self.assertEqual(state.validate(self.data),[])
 def test_duplicate_slot_rejected(self): self.data['slots'].append(self.data['slots'][0]); self.assertIn('CURRENT_STATE_ID',state.validate(self.data))
 def test_fake_physical_pass_rejected(self): self.data['physical_acceptance_claimed']=True; self.assertTrue(state.validate(self.data))
 def test_missing_evidence_rejected(self): self.data['slots'][0].update(status='HOST_VERIFIED',evidence=[]); self.assertTrue(state.validate(self.data))
 def test_target_not_closed_by_host(self): self.data['slots'][0].update(id='47.9.1',status='HOST_VERIFIED',evidence=['tools/recovery_guard.py']); self.assertTrue(state.validate(self.data))
 def test_unknown_status_rejected(self): self.data['slots'][0]['status']='RUNNING'; self.assertTrue(state.validate(self.data))
 def test_evidence_traversal_rejected(self): self.data['slots'][0]['evidence']=['../secret']; self.assertTrue(state.validate(self.data))
 def test_render_current(self): self.assertEqual(state.render(self.data),(ROOT/'docs/CURRENT_STATE.md').read_text())
class TarTests(unittest.TestCase):
 def make(self,entries):
  d=tempfile.TemporaryDirectory(); self.addCleanup(d.cleanup); p=Path(d.name)/'test.tar.bz2'
  with tarfile.open(p,'w:bz2') as a:
   for name,kind in entries:
    i=tarfile.TarInfo(name); i.mode=0o755
    if kind=='link': i.type=tarfile.SYMTYPE; i.linkname='/tmp/unsafe'; a.addfile(i)
    else: i.size=3; a.addfile(i,io.BytesIO(b'abc'))
  return p
 def test_normal_tar_preserves_executable(self):
  p=self.make([('repo/entry.sh','file')]); self.assertEqual(archive.inspect_tar(p)['status'],'PASS')
  dest=p.parent/'out'; dest.mkdir(); archive.extract_tar_preserving_permissions(p,dest); self.assertEqual((dest/'repo/entry.sh').stat().st_mode&0o777,0o755)
 def test_duplicates_refused(self): self.assertEqual(archive.inspect_tar(self.make([('r/f','file'),('r/f','file')]))['status'],'FAIL')
 def test_links_refused(self): self.assertEqual(archive.inspect_tar(self.make([('r/l','link')]))['status'],'FAIL')
 def test_traversal_refused(self): self.assertEqual(archive.inspect_tar(self.make([('r/../f','file')]))['status'],'FAIL')
 def test_two_roots_refused(self): self.assertEqual(archive.inspect_tar(self.make([('r/f','file'),('s/f','file')]))['status'],'FAIL')
 def test_empty_refused(self): self.assertEqual(archive.inspect_tar(self.make([]))['status'],'FAIL')
