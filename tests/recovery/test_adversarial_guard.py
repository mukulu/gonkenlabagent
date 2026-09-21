import io
import json
from pathlib import Path
import tarfile
import unittest
import test_recovery_guard as base

m = base.m


class AdversarialTests(unittest.TestCase):
    setUp = base.RecoveryTests.setUp
    g = base.RecoveryTests.g
    create = base.RecoveryTests.create
    modify_archive = base.RecoveryTests.modify_archive
    assert_refusal = base.RecoveryTests.assert_refusal

    def alter_meta(self, edit):
        self.create()
        def change(members):
            result=[]
            for name,data in members:
                if name==m.META:
                    value=json.loads(data); edit(value); data=json.dumps(value).encode()
                result.append((name,data))
            return result
        return self.modify_archive(change)

    def test_list_instead_of_symbolic_target_refused(self):
        sha=self.alter_meta(lambda d:d['repository']['refs']['refs/remotes/origin/HEAD'].update(symbolic_target=[]))
        self.assert_refusal('SYMBOLIC_REF_INVALID',lambda:m.verify(self.archive,sha,self.head,30))

    def test_list_instead_of_branch_refused(self):
        sha=self.alter_meta(lambda d:d['repository'].update(branch=[]))
        self.assert_refusal('HEAD_BRANCH_MISMATCH',lambda:m.verify(self.archive,sha,self.head,30))

    def test_wrong_tree_cleans_failed_restore(self):
        sha=self.alter_meta(lambda d:d['repository'].update(tree='0'*40)); dest=self.root/'target'
        self.assert_refusal('RESTORED_IDENTITY_MISMATCH',lambda:m.restore(self.archive,dest,sha,self.head,30))
        self.assertFalse(dest.exists())

    def test_physical_claim_cannot_be_injected(self):
        sha=self.alter_meta(lambda d:d.update(physical_acceptance_claimed=True))
        self.assert_refusal('FALSE_PHYSICAL_CLAIM',lambda:m.verify(self.archive,sha,self.head,30))

    def test_schema_is_versioned_not_guessed(self):
        sha=self.alter_meta(lambda d:d.update(schema='unknown-schema'))
        self.assert_refusal('SCHEMA_UNSUPPORTED',lambda:m.verify(self.archive,sha,self.head,30))

    def test_duplicate_json_key_rejected(self):
        self.create()
        def change(ms):
            return [(n,b'{"schema":"conflict",'+b[1:] if n==m.META else b) for n,b in ms]
        sha=self.modify_archive(change)
        self.assert_refusal('DUPLICATE_JSON_KEY',lambda:m.verify(self.archive,sha,self.head,30))

    def test_missing_bundle_rejected(self):
        self.create(); sha=self.modify_archive(lambda ms:[(n,b) for n,b in ms if n==m.META])
        self.assert_refusal('INCOMPLETE_ARCHIVE',lambda:m.verify(self.archive,sha,self.head,30))

    def test_symlink_archive_member_rejected(self):
        self.create(); self.archive.unlink()
        with tarfile.open(self.archive,'w:bz2') as tf:
            info=tarfile.TarInfo(m.META); info.type=tarfile.SYMTYPE; info.linkname='/tmp/outside'
            tf.addfile(info)
        sha=m.digest(self.archive)
        self.assert_refusal('UNSAFE_MEMBER_TYPE',lambda:m.verify(self.archive,sha,self.head,30))

    def test_incremental_bundle_not_accepted_as_self_contained(self):
        self.create(); bundle=self.root/'incremental.bundle'
        self.g('bundle','create',str(bundle),self.first+'..main')
        binary=bundle.read_bytes()
        def change(ms):
            result=[]
            for n,b in ms:
                if n==m.BUNDLE: b=binary
                if n==m.META:
                    d=json.loads(b); d['bundle_sha256']=m.digest(bundle); b=json.dumps(d).encode()
                result.append((n,b))
            return result
        sha=self.modify_archive(change); dest=self.root/'target'
        self.assert_refusal('COMMAND_FAILED',lambda:m.restore(self.archive,dest,sha,self.head,30))
        self.assertFalse(dest.exists())

    def test_replace_refs_are_not_silent_revision_rewrites(self):
        self.g('update-ref','refs/replace/'+self.first,self.head)
        self.assert_refusal('REPLACE_REFS_UNSUPPORTED',self.create)
