import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / 'tools' / 'recovery_guard.py'
spec = importlib.util.spec_from_file_location('recovery_guard', SCRIPT)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
ORIGIN = 'git@github.com:mukulu/gonkenlabagent.git'


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'source'
        self.repo.mkdir()
        self.g('init', '-q', '-b', 'main')
        self.g('config', 'user.name', 'John Francis Mukulu')
        self.g('config', 'user.email', 'john.f.mukulu@gmail.com')
        self.g('remote', 'add', 'origin', ORIGIN)
        (self.repo/'entry.sh').write_text('#!/bin/sh\necho checked\n')
        (self.repo/'entry.sh').chmod(0o755)
        (self.repo/'content.txt').write_text('original\n')
        (self.repo/'.gitignore').write_text('ignored/\n')
        self.g('add', '.')
        self.g('commit', '-q', '-m', 'first')
        self.first = self.g('rev-parse', 'HEAD')
        self.g('tag', '-a', 'checkpoint/test', '-m', 'annotated checkpoint')
        self.g('branch', 'retained-history')
        (self.repo/'content.txt').write_text('second\n')
        self.g('commit', '-q', '-am', 'second')
        self.head = self.g('rev-parse', 'HEAD')
        self.g('update-ref', 'refs/remotes/origin/main', self.head)
        self.g('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main')
        self.g('config', 'branch.main.remote', 'origin')
        self.g('config', 'branch.main.merge', 'refs/heads/main')
        self.archive = self.root/'test.tar.bz2'

    def g(self, *args, repo=None):
        return subprocess.check_output(['git','-C',str(repo or self.repo),*args],
            stderr=subprocess.PIPE, env={**os.environ,'GIT_CONFIG_GLOBAL':os.devnull,
                                        'GIT_CONFIG_NOSYSTEM':'1'}).decode().strip()

    def create(self, **kwargs):
        return m.create(self.repo,self.archive,'RG-test','Recover exact next slot',
                        kwargs.get('expected_head',self.head),30)

    def modify_archive(self, mutation):
        with tarfile.open(self.archive, 'r:bz2') as tf:
            members = [(x.name,tf.extractfile(x).read()) for x in tf]
        members = mutation(members)
        self.archive.unlink()
        with tarfile.open(self.archive, 'w:bz2') as tf:
            for name,data in members:
                info=tarfile.TarInfo(name); info.size=len(data)
                tf.addfile(info,io.BytesIO(data))
        return m.digest(self.archive)

    def assert_refusal(self, code, call):
        with self.assertRaisesRegex(m.RecoveryError, code):
            call()

    def test_roundtrip_preserves_history_refs_modes_identity_and_tracking(self):
        result=self.create()
        self.assertFalse(result['delivery_verified'])
        out=self.root/'restored'
        m.restore(self.archive,out,result['archive_sha256'],self.head,30)
        for args in [('rev-parse','HEAD'),('rev-parse','HEAD^{tree}'),
                     ('for-each-ref','--format=%(refname) %(objectname) %(symref)'),
                     ('log','--all','--format=%H %an %ae %cn %ce'),
                     ('config','--get','branch.main.merge')]:
            self.assertEqual(self.g(*args), self.g(*args,repo=out))
        self.assertTrue(os.access(out/'entry.sh',os.X_OK))
        self.assertEqual(self.g('config','--get','remote.origin.url',repo=out),ORIGIN)
        self.assertEqual(self.g('status','--porcelain',repo=out),'')

    def test_no_original_repository_needed(self):
        result=self.create(); shutil.rmtree(self.repo)
        out=m.verify(self.archive,result['archive_sha256'],self.head,30)
        self.assertEqual(out['status'],'COLD_RESTORE_VERIFIED')

    def test_rejects_wrong_checkpoint_commit(self):
        self.assert_refusal('EXPECTED_COMMIT_MISMATCH',lambda:self.create(expected_head=self.first))
        self.assertFalse(self.archive.exists())

    def test_verify_rejects_wrong_expected_commit(self):
        r=self.create()
        self.assert_refusal('EXPECTED_COMMIT_MISMATCH',
            lambda:m.verify(self.archive,r['archive_sha256'],self.first,30))

    def test_corrupt_checksum(self):
        self.create()
        self.assert_refusal('ARCHIVE_SHA256_MISMATCH',
            lambda:m.verify(self.archive,'0'*64,self.head,30))

    def test_existing_output_never_overwritten(self):
        self.create(); before=self.archive.read_bytes()
        self.assert_refusal('OUTPUT_EXISTS',self.create)
        self.assertEqual(self.archive.read_bytes(),before)

    def test_existing_restore_destination_not_changed(self):
        r=self.create(); dest=self.root/'keep'; dest.mkdir(); (dest/'saved').write_text('safe')
        self.assert_refusal('DESTINATION_EXISTS',
            lambda:m.restore(self.archive,dest,r['archive_sha256'],self.head,30))
        self.assertEqual((dest/'saved').read_text(),'safe')

    def test_uncommitted_change_rejected(self):
        (self.repo/'content.txt').write_text('unfinished')
        self.assert_refusal('UNCOMMITTED_OR_UNTRACKED_FILES',self.create)

    def test_untracked_change_rejected(self):
        (self.repo/'new.txt').write_text('unfinished')
        self.assert_refusal('UNCOMMITTED_OR_UNTRACKED_FILES',self.create)

    def test_ignored_secret_hooks_and_credentials_not_exported(self):
        (self.repo/'ignored').mkdir(); (self.repo/'ignored'/'secret').write_text('PRIVATE_CANARY')
        (self.repo/'.git'/'hooks'/'post-checkout').write_text('#!/bin/sh\ntouch /tmp/UNSAFE_CANARY\n')
        (self.repo/'.git'/'hooks'/'post-checkout').chmod(0o755)
        self.g('config','credential.helper','!echo CREDENTIAL_CANARY')
        r=self.create(); out=self.root/'restored'
        m.restore(self.archive,out,r['archive_sha256'],self.head,30)
        self.assertFalse((out/'ignored').exists())
        self.assertFalse((out/'.git'/'hooks'/'post-checkout').exists())
        self.assertNotIn('CREDENTIAL_CANARY',(out/'.git'/'config').read_text())
        self.assertFalse(Path('/tmp/UNSAFE_CANARY').exists())

    def test_credential_origin_refused(self):
        self.g('remote','set-url','origin','https://token:secret@github.com/mukulu/gonkenlabagent.git')
        self.assert_refusal('CREDENTIAL_BEARING_OR_UNSUPPORTED_ORIGIN',self.create)

    def test_assume_unchanged_cannot_hide_mutation(self):
        self.g('update-index','--assume-unchanged','content.txt')
        (self.repo/'content.txt').write_text('hidden')
        self.assert_refusal('HIDDEN_INDEX_STATE_UNSUPPORTED',self.create)

    def test_shallow_repository_refused(self):
        (self.repo/'.git'/'shallow').write_text(self.first+'\n')
        self.assert_refusal('SHALLOW_REPOSITORY_UNSUPPORTED',self.create)

    def test_symlink_tree_refused(self):
        (self.repo/'unsafe').symlink_to('/tmp')
        self.g('add','unsafe'); self.g('commit','-qm','symlink'); self.head=self.g('rev-parse','HEAD')
        self.assert_refusal('SYMLINK_CHECKOUT_UNSUPPORTED',self.create)

    def test_detached_head_supported(self):
        self.g('checkout','-q','--detach',self.head)
        r=self.create(); out=self.root/'restore'
        m.restore(self.archive,out,r['archive_sha256'],self.head,30)
        self.assertEqual(self.g('rev-parse','--abbrev-ref','HEAD',repo=out),'HEAD')

    def test_duplicate_member_rejected(self):
        self.create(); sha=self.modify_archive(lambda ms: ms+[ms[0]])
        self.assert_refusal('UNEXPECTED_OR_DUPLICATE_MEMBER',lambda:m.verify(self.archive,sha,self.head,30))

    def test_path_traversal_member_rejected(self):
        self.create(); sha=self.modify_archive(lambda ms: ms+[('../outside',b'bad')])
        self.assert_refusal('UNEXPECTED_OR_DUPLICATE_MEMBER',lambda:m.verify(self.archive,sha,self.head,30))
        self.assertFalse((self.root/'outside').exists())

    def test_changed_bundle_rejected(self):
        self.create(); sha=self.modify_archive(lambda ms:[(n,b+b'x' if n==m.BUNDLE else b) for n,b in ms])
        self.assert_refusal('BUNDLE_SHA256_MISMATCH',lambda:m.verify(self.archive,sha,self.head,30))

    def test_source_change_during_export_refused(self):
        original=m.inspect_repo; calls=[0]
        def drift(repo,runner):
            state=original(repo,runner); calls[0]+=1
            if calls[0]>1: state['tree']='0'*40
            return state
        with patch.object(m,'inspect_repo',side_effect=drift):
            self.assert_refusal('SOURCE_CHANGED_DURING_EXPORT',self.create)
        self.assertFalse(self.archive.exists())

    def test_invalid_artifact_does_not_create_restore_directory(self):
        r=self.create(); dest=self.root/'out'
        self.assert_refusal('EXPECTED_COMMIT_MISMATCH',
            lambda:m.restore(self.archive,dest,r['archive_sha256'],self.first,30))
        self.assertFalse(dest.exists())

    def test_lfs_pointer_rejected(self):
        (self.repo/'large').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:'+'0'*64+'\nsize 99\n')
        self.g('add','large'); self.g('commit','-qm','pointer'); self.head=self.g('rev-parse','HEAD')
        self.assert_refusal('LFS_OBJECT_BACKUP_UNSUPPORTED',self.create)

    def test_lfs_documentation_is_not_an_external_object(self):
        (self.repo/'docs.md').write_text('Example only:\nversion https://git-lfs.github.com/spec/v1\n')
        self.g('add','docs.md'); self.g('commit','-qm','documentation'); self.head=self.g('rev-parse','HEAD')
        self.create()

    def test_submodule_gitlink_refused(self):
        self.g('update-index','--add','--cacheinfo','160000',self.first,'submodule')
        self.g('commit','-qm','gitlink'); self.head=self.g('rev-parse','HEAD')
        (self.repo/'submodule').mkdir()
        self.assert_refusal('SUBMODULE_BACKUP_UNSUPPORTED',self.create)

    def test_timeout_is_bounded(self):
        start=time.monotonic()
        self.assert_refusal('COMMAND_TIMEOUT',lambda:m.Runner(.1).run([sys.executable,'-c','import time; time.sleep(30)']))
        self.assertLess(time.monotonic()-start,3)

    def test_invalid_cli_exit_is_nonzero_and_truthful(self):
        p=subprocess.run([sys.executable,str(SCRIPT),'verify','--archive',str(self.archive),
            '--sha256','0'*64,'--expected-commit',self.head],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,2)
        self.assertEqual(json.loads(p.stderr)['status'],'REFUSED')


if __name__=='__main__':
    unittest.main()
