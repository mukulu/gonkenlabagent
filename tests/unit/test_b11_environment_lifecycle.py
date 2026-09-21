"""No real hardware: isolate signals and AF_UNIX exclusive ownership."""
from __future__ import annotations
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from gonken_agent.environment.server import EnvironmentUnixServer

class SocketOwnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'control.sock'
        self.closed=[];self.core=SimpleNamespace(shutdown_safe_off=lambda:self.closed.append('OFF'))
    def new(self):return EnvironmentUnixServer(self.path,self.core)
    def test_second_server_cannot_replace_first(self):
        first=self.new();self.addCleanup(first.server_close);inode=self.path.stat().st_ino
        with self.assertRaisesRegex(OSError,'ALREADY_OWNED'):self.new()
        self.assertEqual(self.path.stat().st_ino,inode);self.assertEqual(self.closed,[])
        first.server_close();first.server_close();self.assertEqual(self.closed,['OFF'])
        second=self.new();second.server_close();self.assertEqual(self.closed,['OFF','OFF'])
    def test_legacy_live_socket_without_lock_is_not_replaced(self):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as live:
            live.bind(str(self.path));live.listen(1);inode=self.path.stat().st_ino
            with self.assertRaisesRegex(OSError,'ALREADY_OWNED'):self.new()
            self.assertEqual(self.path.stat().st_ino,inode)
    def test_stale_socket_is_recovered(self):
        stale=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);stale.bind(str(self.path));stale.close()
        server=self.new();self.assertTrue(self.path.exists());server.server_close()
        self.assertFalse(self.path.exists());self.assertTrue(Path(str(self.path)+'.owner.lock').exists())
    def test_symlink_socket_is_rejected(self):
        target=Path(self.tmp.name)/'other.sock'
        stale=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);stale.bind(str(target));stale.close()
        self.path.symlink_to(target)
        with self.assertRaisesRegex(OSError,'PATH_UNSAFE'):self.new()
        self.assertTrue(target.exists());self.assertTrue(self.path.is_symlink())
    def test_lock_symlink_and_non_socket_refused(self):
        target=Path(self.tmp.name)/'private';target.write_text('KEEP')
        lock=Path(str(self.path)+'.owner.lock');lock.symlink_to(target)
        with self.assertRaises(OSError):self.new()
        self.assertEqual(target.read_text(),'KEEP');lock.unlink()
        self.path.write_text('KEEP')
        with self.assertRaisesRegex(OSError,'PATH_UNSAFE'):self.new()
        self.assertEqual(self.path.read_text(),'KEEP')
    def test_bind_failure_releases_lock_without_hardware_cleanup(self):
        with patch.object(EnvironmentUnixServer,'server_bind',side_effect=OSError('bind failure')):
            with self.assertRaisesRegex(OSError,'bind failure'):self.new()
        self.assertEqual(self.closed,[])
        server=self.new();server.server_close()
        self.assertEqual(self.closed,['OFF'])
    def test_close_does_not_unlink_replacement_socket(self):
        server=self.new();self.path.unlink()
        replacement=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);replacement.bind(str(self.path))
        try:
            inode=self.path.stat().st_ino;server.server_close()
            self.assertEqual(self.path.stat().st_ino,inode)
        finally:replacement.close()

class SignalCleanupTests(unittest.TestCase):
    def test_sigterm_and_sigint_call_safe_off_and_close(self):
        child='''
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from gonken_agent.environment.server import EnvironmentUnixServer
from gonken_agent.environment.daemon import EnvironmentDaemon
path=Path(sys.argv[1])
def stop():
    with (path/'actions.txt').open('a') as out: out.write('safe_off\\nrelease\\n')
core=SimpleNamespace(shutdown_safe_off=stop)
server=EnvironmentUnixServer(path/'control.sock', core)
class Poller:
    def start(self): (path/'ready').write_text('ready')
    def stop(self): pass
EnvironmentDaemon(server, polling_loop=Poller()).serve_forever()
'''
        for signum in (signal.SIGTERM,signal.SIGINT):
            with self.subTest(signal=signum),tempfile.TemporaryDirectory() as name:
                path=Path(name)
                env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / 'src'))
                proc=subprocess.Popen([sys.executable,'-c',child,name],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
                try:
                    until=time.monotonic()+4
                    while not (path/'ready').exists() and proc.poll() is None and time.monotonic()<until:time.sleep(.02)
                    if not (path/'ready').exists():
                        if proc.poll() is None: proc.kill()
                        _, stderr = proc.communicate(timeout=2)
                        self.fail('signal fixture did not start: ' + stderr.decode(errors='replace'))
                    proc.send_signal(signum);out,err=proc.communicate(timeout=4)
                    self.assertEqual(proc.returncode,0,err.decode());self.assertFalse((path/'control.sock').exists())
                    self.assertEqual((path/'actions.txt').read_text(),'safe_off\nrelease\n')
                finally:
                    if proc.poll() is None:proc.kill();proc.communicate(timeout=2)

if __name__=='__main__':unittest.main()
