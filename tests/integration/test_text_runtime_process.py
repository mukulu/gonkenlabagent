import http.client
import json
import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from gonken_agent.config import load_config
from gonken_agent.llm.ollama import OllamaClient, OllamaError
from gonken_agent.runtime import Cancelled
from gonken_agent.dashboard import Snapshot, server

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/'tests/fixtures/grounding'


class LocalAPI(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,data,status=200):
        raw=json.dumps(data).encode()
        self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers()
        if getattr(self.server,'delay_body',0):
            self.server.body_headers_sent.set()
            time.sleep(self.server.delay_body)
        try:self.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self):
        self.server.requests.append(self.path)
        self.reply({'models':[{'name':self.server.model,'digest':'a'*64}]})
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(body)
        self.server.entered.set()
        if self.server.delay:time.sleep(self.server.delay)
        self.reply({'model':self.server.model,'done':True,'message':{'content':'{"answer":"Two hours.","source_ids":[],"abstain":true}'}},self.server.status)


class LocalNetworkTests(unittest.TestCase):
    def setUp(self):
        self.api=ThreadingHTTPServer(('127.0.0.1',0),LocalAPI)
        self.api.daemon_threads=True
        self.api.model=load_config(site_path=None,environ={}).config.llm.model
        self.api.requests=[];self.api.delay=0;self.api.status=200;self.api.entered=threading.Event()
        self.worker=threading.Thread(target=lambda:self.api.serve_forever(poll_interval=.01),daemon=True);self.worker.start()
        self.addCleanup(self.api.server_close);self.addCleanup(self.api.shutdown)
        cfg=load_config(site_path=None,environ={}).config.llm
        self.config=replace(cfg,base_url=f'http://127.0.0.1:{self.api.server_port}')
    def test_works_when_dns_proxy_and_external_connections_forbidden(self):
        client=OllamaClient(self.config)
        original=socket.socket.connect
        connections=[]
        def connect(sock,address):
            if address[0]!='127.0.0.1':raise AssertionError('external connection')
            connections.append(address)
            return original(sock,address)
        with patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')),patch('socket.socket.connect',connect),patch.dict(os.environ,{'HTTP_PROXY':'http://external.invalid:80','HTTPS_PROXY':'http://external.invalid:80'}):
            self.assertEqual(client.model_identity(threading.Event())['digest'],'a'*64)
            client.chat([{'role':'user','content':'test'}],threading.Event())
        self.assertEqual(len(connections),2)
        self.assertEqual(self.api.requests[-1]['model'],self.config.model)
        self.assertFalse(self.api.requests[-1]['stream'])
        client.close()
    def test_non_loopback_hostname_redirect_path_and_credentials_refused(self):
        for endpoint in ['http://example.com','http://localhost:11434','http://192.168.0.2','https://127.0.0.1','http://user@127.0.0.1','http://127.0.0.1/api']:
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ValueError):OllamaClient(replace(self.config,base_url=endpoint))
        self.api.status=302
        with self.assertRaises(OllamaError):OllamaClient(self.config).chat([],threading.Event())
        self.assertEqual(len(self.api.requests),1)
    def test_cancel_timeout_overload_and_single_request_lock(self):
        self.api.delay=.5
        client=OllamaClient(self.config,timeout=2)
        cancel=threading.Event();errors=[]
        def request():
            try:client.chat([],cancel)
            except Exception as exc:errors.append(exc)
        worker=threading.Thread(target=request);worker.start()
        self.assertTrue(self.api.entered.wait(1))
        with self.assertRaisesRegex(OllamaError,'BUSY'):client.chat([],threading.Event())
        cancel.set();worker.join(1)
        self.assertFalse(worker.is_alive());self.assertIsInstance(errors[0],Cancelled)
        client.close()
        short=OllamaClient(self.config,timeout=.05)
        with self.assertRaisesRegex(OllamaError,'TIMEOUT'):short.chat([],threading.Event())
        short.close()
        self.api.delay=0;self.api.status=503
        with self.assertRaisesRegex(OllamaError,'OVERLOADED'):OllamaClient(self.config).chat([],threading.Event())
    def test_cancellation_after_connection_close_response_headers(self):
        # HTTP/1.0 makes HTTPConnection detach its socket before body consumption.
        self.api.delay_body=.5;self.api.body_headers_sent=threading.Event()
        client=OllamaClient(self.config,timeout=2);cancel=threading.Event();errors=[]
        def request():
            try:client.chat([],cancel)
            except Exception as exc:errors.append(exc)
        worker=threading.Thread(target=request);worker.start()
        self.assertTrue(self.api.body_headers_sent.wait(1))
        time.sleep(.03)
        cancel.set();worker.join(.3)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(errors[0],Cancelled)
        client.close()
    def test_response_limit_and_malformed_model_identity(self):
        tiny=OllamaClient(self.config,max_response=10)
        with self.assertRaises(OllamaError):tiny.model_identity(threading.Event())
        tiny.close()
        client=OllamaClient(self.config)
        with patch.object(client,'request',return_value={'models':None}):
            with self.assertRaises(OllamaError):client.model_identity(threading.Event())
        client.close()


class DashboardHTTPTests(unittest.TestCase):
    def test_routes_host_origin_content_and_no_mutations(self):
        snapshot=Snapshot(transient=True)
        snapshot.update({'status':'READY'},transcript='<script>alert(1)</script>',answer='answer')
        httpd=server(snapshot,port=0)
        thread=threading.Thread(target=lambda:httpd.serve_forever(poll_interval=.01),daemon=True);thread.start()
        try:
            def request(method,path,headers={}):
                c=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=2)
                c.request(method,path,headers=headers);r=c.getresponse();data=r.read();status=r.status;h=dict(r.getheaders());c.close()
                return status,data,h
            status,data,headers=request('GET','/')
            self.assertEqual(status,200);self.assertNotIn(b'alert',data)
            self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
            self.assertEqual(request('GET','/api/status')[0],200)
            self.assertEqual(request('POST','/api/status')[0],405)
            self.assertEqual(request('DELETE','/')[0],405)
            self.assertEqual(request('GET','/update')[0],404)
            self.assertEqual(request('GET','/api/status',{'Host':'evil.example'})[0],403)
            self.assertEqual(request('GET','/api/status',{'Origin':'https://evil.example'})[0],403)
            snapshot.clear();self.assertNotIn(b'alert',request('GET','/api/status')[1])
        finally:httpd.shutdown();httpd.server_close();thread.join(1)
        with self.assertRaises(ValueError):server(snapshot,bind='0.0.0.0')


class TextCLIProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.index=self.root/'index.json'
        self.env=os.environ.copy();self.env['PYTHONPATH']=str(ROOT/'src')
        self.common=['--no-site','--set',f'paths.corpus_dir={FIXTURES / "corpus"}','--index',str(self.index)]
        result=self.cli('index','build',*self.common,'--calibration',str(FIXTURES/'calibration.json'))
        self.assertEqual(result.returncode,0,result.stderr)
    def cli(self,*args):
        return subprocess.run([sys.executable,'-m','gonken_agent',*args],cwd=ROOT,env=self.env,capture_output=True,text=True,timeout=10)
    def test_build_verify_ask_unknown_doctor_and_no_content_telemetry(self):
        self.assertEqual(self.cli('index','verify',*self.common).returncode,0)
        telemetry=self.root/'telemetry.jsonl'
        result=self.cli('ask','What is the booking duration for the Atlas bench?',*self.common,'--extractive','--telemetry',str(telemetry))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('two hours',json.loads(result.stdout)['answer'])
        self.assertNotIn('two hours',telemetry.read_text())
        unknown=self.cli('ask','Explain coral bleaching.',*self.common,'--extractive')
        self.assertTrue(json.loads(unknown.stdout)['abstain'])
        doctor=self.cli('doctor',*self.common)
        self.assertEqual(doctor.returncode,2)
        self.assertNotIn(str(FIXTURES),doctor.stdout)
    def test_text_session_multiple_lines_eof_and_signal_shutdown(self):
        argv=[sys.executable,'-m','gonken_agent','run','--text-only','--extractive',*self.common]
        result=subprocess.run(argv,input='Atlas bench booking duration?\nExplain coral bleaching.\n',capture_output=True,text=True,env=self.env,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        rows=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(rows),3);self.assertFalse(rows[1]['abstain']);self.assertTrue(rows[2]['abstain'])
        for sig in (signal.SIGTERM,signal.SIGINT):
            p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=self.env)
            try:
                readable,_,_=select.select([p.stdout],[],[],3)
                self.assertTrue(readable);self.assertIn('text-diagnostic',p.stdout.readline())
                p.send_signal(sig);out,err=p.communicate(timeout=3)
                self.assertEqual(p.returncode,0,err)
                self.assertNotIn('Traceback',err)
            finally:
                if p.poll() is None:p.kill();p.wait()
    def test_invalid_index_and_calibration_fail_categorically(self):
        self.index.write_text('[]')
        result=self.cli('ask','question',*self.common,'--extractive')
        self.assertEqual(result.returncode,1)
        self.assertNotIn('Traceback',result.stderr)
        self.assertNotIn(str(self.root),result.stderr)
