"""Direct numeric-loopback HTTP only; never use proxies, DNS or redirects."""
import http.client
import ipaddress
import json
import socket
import threading
import time
from urllib.parse import urlsplit
from ..runtime import Cancelled


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config, timeout=45, max_response=1024 * 1024):
        endpoint = urlsplit(config.base_url)
        try: loopback = ipaddress.ip_address(endpoint.hostname).is_loopback
        except ValueError: loopback = False
        if endpoint.scheme != 'http' or not loopback or endpoint.username or endpoint.password or endpoint.path not in ('', '/') or endpoint.query or endpoint.fragment:
            raise ValueError('numeric HTTP loopback endpoint required')
        if not 0 < timeout <= 120 or not 0 < max_response <= 4 * 1024 * 1024:
            raise ValueError('invalid HTTP bounds')
        self.config, self.endpoint = config, endpoint
        self.timeout, self.max_response = timeout, max_response
        self._lock = threading.Lock()
        self._active = None
        self._transport = None
        self._closed = False

    def _connection(self):
        # Construct a numeric socket directly, bypassing getaddrinfo entirely.
        family = socket.AF_INET6 if ':' in self.endpoint.hostname else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try: sock.connect((self.endpoint.hostname, self.endpoint.port or 80))
        except BaseException:
            sock.close()
            raise
        connection = http.client.HTTPConnection(self.endpoint.hostname, self.endpoint.port or 80, timeout=self.timeout)
        connection.sock = sock
        self._transport = sock
        return connection

    def request(self, method, path, payload, cancel):
        if method not in {'GET', 'POST'} or path not in {'/api/tags', '/api/chat', '/api/version'}:
            raise ValueError('unapproved local API route')
        if not self._lock.acquire(blocking=False):
            raise OllamaError('OLLAMA_BUSY')
        done = threading.Event()
        expired = threading.Event()
        deadline = time.monotonic() + self.timeout
        def interrupt():
            while not done.wait(.02):
                if time.monotonic() >= deadline:
                    expired.set()
                if cancel.is_set() or self._closed or expired.is_set():
                    transport = self._transport
                    if transport:
                        try: transport.shutdown(socket.SHUT_RDWR)
                        except OSError: pass
                    return
        watcher = threading.Thread(target=interrupt, daemon=True)
        response = None
        try:
            if self._closed or cancel.is_set(): raise Cancelled()
            watcher.start()
            self._active = self._connection()
            if cancel.is_set() or self._closed: raise Cancelled()
            if expired.is_set(): raise OllamaError('OLLAMA_TIMEOUT')
            body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
            if body and len(body) > 128 * 1024: raise OllamaError('OLLAMA_REQUEST_LIMIT')
            self._active.request(method, path, body=body, headers={'Content-Type': 'application/json'})
            response = self._active.getresponse()
            if response.status != 200:
                code = {404:'OLLAMA_MODEL_MISSING', 503:'OLLAMA_OVERLOADED'}.get(response.status, 'OLLAMA_HTTP_ERROR')
                raise OllamaError(code)
            data = response.read(self.max_response + 1)
            if len(data) > self.max_response: raise OllamaError('OLLAMA_RESPONSE_LIMIT')
            if cancel.is_set(): raise Cancelled()
            if expired.is_set(): raise OllamaError('OLLAMA_TIMEOUT')
            result = json.loads(data)
            if not isinstance(result, dict): raise OllamaError('OLLAMA_MALFORMED_RESPONSE')
            return result
        except (socket.timeout, TimeoutError) as exc:
            if cancel.is_set(): raise Cancelled() from exc
            raise OllamaError('OLLAMA_TIMEOUT') from exc
        except (OSError, http.client.HTTPException, ValueError) as exc:
            if cancel.is_set(): raise Cancelled() from exc
            if expired.is_set(): raise OllamaError('OLLAMA_TIMEOUT') from exc
            raise OllamaError('OLLAMA_UNAVAILABLE_OR_MALFORMED') from exc
        finally:
            done.set()
            if response: response.close()
            if self._active: self._active.close()
            self._active = None
            self._transport = None
            if watcher.ident: watcher.join(timeout=.2)
            self._lock.release()

    def model_identity(self, cancel):
        data = self.request('GET', '/api/tags', None, cancel)
        if not isinstance(data.get('models'), list): raise OllamaError('OLLAMA_MALFORMED_RESPONSE')
        matches = [m for m in data['models'] if isinstance(m, dict) and m.get('name') == self.config.model]
        if len(matches) != 1: raise OllamaError('OLLAMA_MODEL_MISSING')
        digest = matches[0].get('digest', '')
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise OllamaError('OLLAMA_MODEL_DIGEST_INVALID')
        return {'model': self.config.model, 'digest': digest}

    def _chat_payload(self, messages, *, structured):
        if not isinstance(messages, list) or len(messages) > 20:
            raise ValueError('bounded chat messages required')
        for item in messages:
            if not isinstance(item, dict) or set(item) != {'role', 'content'}:
                raise ValueError('invalid chat message')
            if item['role'] not in {'system', 'user', 'assistant'} or not isinstance(item['content'], str):
                raise ValueError('invalid chat message')
            if not item['content'].strip() or len(item['content']) > 16384:
                raise ValueError('chat message exceeds bounds')
        payload = {'model': self.config.model, 'messages': messages, 'stream': False,
                   'think': False, 'keep_alive': self.config.keep_alive,
                   'options': {'num_ctx': self.config.context_tokens,
                               'num_predict': self.config.max_output_tokens, 'temperature': 0}}
        if structured:
            payload['format'] = 'json'
        return payload

    def _chat_result(self, messages, cancel, *, structured):
        data = self.request('POST', '/api/chat', self._chat_payload(messages, structured=structured), cancel)
        if data.get('model') != self.config.model or data.get('done') is not True:
            raise OllamaError('OLLAMA_MODEL_OR_COMPLETION_MISMATCH')
        if not isinstance(data.get('message'), dict):
            raise OllamaError('OLLAMA_MALFORMED_RESPONSE')
        content = data['message'].get('content')
        if not isinstance(content, str) or not content.strip():
            raise OllamaError('OLLAMA_MALFORMED_RESPONSE')
        return content

    def chat(self, messages, cancel):
        return self._chat_result(messages, cancel, structured=True)

    def chat_text(self, messages, cancel):
        """Return normal spoken-conversation text with Qwen thinking disabled."""
        return self._chat_result(messages, cancel, structured=False)

    def close(self):
        self._closed = True
        if self._transport:
            try: self._transport.shutdown(socket.SHUT_RDWR)
            except OSError: pass
