"""Read-only numeric-loopback dashboard with optional in-memory content."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from .telemetry import validate_event

HTML = b'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>GonKenLab Agent</title><body><h1>GonKenLab Agent</h1><p>Local diagnostic dashboard</p><pre id="status">Loading...</pre><script src="/app.js"></script></body></html>'''
JS = b'''async function refresh(){try{const response=await fetch('/api/status',{cache:'no-store'});document.getElementById('status').textContent=JSON.stringify(await response.json(),null,2);}catch(e){document.getElementById('status').textContent='Dashboard unavailable';}}refresh();setInterval(refresh,2000);'''


class Snapshot:
    def __init__(self, *, transient=False, allowed_source_ids=()):
        self.transient, self.allowed = transient, frozenset(allowed_source_ids)
        self._lock = threading.Lock()
        self._metrics = {'state':'BOOTING','status':'DEGRADED'}
        self._content = None

    def update(self, metrics, *, transcript=None, answer=None):
        metrics = validate_event(metrics,self.allowed)
        with self._lock:
            self._metrics = metrics
            self._content = None
            if self.transient and transcript is not None and answer is not None:
                if not isinstance(transcript,str) or not isinstance(answer,str) or max(len(transcript),len(answer)) > 4096:
                    raise ValueError('transient content exceeds bound')
                self._content = {'transcript':transcript,'answer':answer}

    def transition(self, state, status):
        values=validate_event({'state':state,'status':status},self.allowed)
        with self._lock:
            self._metrics.update(values)
            if state=='STOPPING': self._content=None

    def read(self):
        with self._lock:
            data = {'metrics':self._metrics,'privacy':{'persistent_content':False,'transient_content':self.transient}}
            if self._content is not None: data['interaction'] = self._content
            return json.loads(json.dumps(data))

    def clear(self):
        with self._lock: self._content = None


def server(snapshot, bind='127.0.0.1', port=8080):
    if bind != '127.0.0.1' or type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('dashboard requires IPv4 loopback')
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(2)
        def log_message(self,*args): pass
        def _reply(self, status, body=b'', kind='text/plain; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header('Referrer-Policy','no-referrer')
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            authority = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != authority or self.headers.get('Origin') not in (None,'http://'+authority):
                return self._reply(403)
            if self.path == '/': return self._reply(200,HTML,'text/html; charset=utf-8')
            if self.path == '/app.js': return self._reply(200,JS,'application/javascript')
            if self.path == '/api/status': return self._reply(200,json.dumps(snapshot.read(),ensure_ascii=True).encode(),'application/json')
            return self._reply(404)
        def do_POST(self): self._reply(405)
        do_PUT = do_DELETE = do_PATCH = do_POST
    return HTTPServer((bind,port),Handler)
