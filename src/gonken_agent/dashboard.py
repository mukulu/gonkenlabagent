"""Read-only numeric-loopback dashboard with optional in-memory content."""
import json
from collections.abc import Mapping
from html import escape
from .identity import IDENTITY
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from .telemetry import validate_event

HTML = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{product}</title><body><h1>{product}</h1><p>Local diagnostic dashboard</p><pre id="status">Loading...</pre><script src="/app.js"></script></body></html>'''.format(product=escape(IDENTITY.product_name)).encode()
JS = b'''async function refresh(){try{const response=await fetch('/api/status',{cache:'no-store'});document.getElementById('status').textContent=JSON.stringify(await response.json(),null,2);}catch(e){document.getElementById('status').textContent='Dashboard unavailable';}}refresh();setInterval(refresh,2000);'''


class Snapshot:
    def __init__(self, *, transient=False, allowed_source_ids=()):
        self.transient, self.allowed = transient, frozenset(allowed_source_ids)
        self._lock = threading.Lock()
        self._metrics = {'state':'BOOTING','status':'DEGRADED'}
        self._content = None
        self._environment = {'status':'DEGRADED','code':'ENVIRONMENT_NOT_REPORTED','physical_evidence':False}

    def update(self, metrics, *, transcript=None, answer=None):
        metrics = validate_event(metrics,self.allowed)
        with self._lock:
            self._metrics = metrics
            self._content = None
            if self.transient and transcript is not None and answer is not None:
                if not isinstance(transcript,str) or not isinstance(answer,str) or max(len(transcript),len(answer)) > 4096:
                    raise ValueError('transient content exceeds bound')
                self._content = {'transcript':transcript,'answer':answer}



    def update_environment(self, environment):
        sanitized = _sanitize_environment(environment)
        with self._lock:
            self._environment = sanitized
    def transition(self, state, status):
        values=validate_event({'state':state,'status':status},self.allowed)
        with self._lock:
            self._metrics.update(values)
            if state=='STOPPING': self._content=None

    def read(self):
        with self._lock:
            data = {'metrics':self._metrics,'environment':self._environment,'privacy':{'persistent_content':False,'transient_content':self.transient}}
            if self._content is not None: data['interaction'] = self._content
            return json.loads(json.dumps(data))

    def clear(self):
        with self._lock: self._content = None


def _sanitize_environment(environment):
    if not isinstance(environment, Mapping):
        raise ValueError('environment status must be an object')
    allowed_status = {'READY', 'DEGRADED', 'FAILED', 'MAINTENANCE'}
    status = environment.get('status', 'DEGRADED')
    if status not in allowed_status:
        raise ValueError('invalid environment status')
    code = environment.get('code', 'ENVIRONMENT_UNKNOWN')
    if not isinstance(code, str) or len(code) > 64 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in code):
        raise ValueError('invalid environment code')
    result = {
        'status': status,
        'code': code,
        'enabled': bool(environment.get('enabled', False)),
        'physical_evidence': bool(environment.get('physical_evidence', False)),
        'target_acceptance': _bounded_token(environment.get('target_acceptance', 'not_established_by_dashboard')),
    }
    capabilities = environment.get('capabilities', {})
    if isinstance(capabilities, Mapping):
        result['capabilities'] = {
            'power_control': bool(capabilities.get('power_control', False)),
            'software_speed_control': bool(capabilities.get('software_speed_control', False)),
            'fan_motion_observed': bool(capabilities.get('fan_motion_observed', False)),
        }
    ipc = environment.get('ipc', {})
    if isinstance(ipc, Mapping):
        result['ipc'] = {
            'status': _bounded_token(ipc.get('status', 'UNKNOWN')),
            'code': _bounded_token(ipc.get('code', 'UNKNOWN')),
            'overall': _bounded_token(ipc.get('overall', 'UNKNOWN')),
            'physical_evidence': bool(ipc.get('physical_evidence', False)),
        }
    for key in ('sensor_backend', 'i2c_address_hex', 'relay_backend'):
        if key in environment:
            result[key] = _bounded_token(environment[key])
    for key in ('i2c_bus', 'relay_bcm'):
        value = environment.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 1000:
            continue
        result[key] = value
    return json.loads(json.dumps(result, allow_nan=False))


def _bounded_token(value):
    if not isinstance(value, str) or len(value) > 96:
        raise ValueError('invalid environment token')
    if any((not c.isalnum()) and c not in '._:/%-' for c in value):
        raise ValueError('invalid environment token')
    return value


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
