"""Direct numeric-loopback HTTP Ollama client.

The client never uses proxies, DNS or redirects.  V04 adds bounded typed tool
calling while retaining the same loopback and response-size boundaries.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import threading
import time
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit

from ..runtime import Cancelled


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config, timeout=45, max_response=1024 * 1024, *, model: str | None = None):
        endpoint = urlsplit(config.base_url)
        try:
            loopback = ipaddress.ip_address(endpoint.hostname).is_loopback
        except ValueError:
            loopback = False
        if (
            endpoint.scheme != "http"
            or not loopback
            or endpoint.username
            or endpoint.password
            or endpoint.path not in ("", "/")
            or endpoint.query
            or endpoint.fragment
        ):
            raise ValueError("numeric HTTP loopback endpoint required")
        if not 0 < timeout <= 120 or not 0 < max_response <= 4 * 1024 * 1024:
            raise ValueError("invalid HTTP bounds")
        self.config, self.endpoint = config, endpoint
        self.model = model or config.model
        if not isinstance(self.model, str) or not self.model.strip() or len(self.model) > 128:
            raise ValueError("invalid Ollama model")
        self.timeout, self.max_response = timeout, max_response
        self._lock = threading.Lock()
        self._active = None
        self._transport = None
        self._closed = False

    def _connection(self):
        # Construct a numeric socket directly, bypassing getaddrinfo entirely.
        family = socket.AF_INET6 if ":" in self.endpoint.hostname else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.endpoint.hostname, self.endpoint.port or 80))
        except BaseException:
            sock.close()
            raise
        connection = http.client.HTTPConnection(
            self.endpoint.hostname, self.endpoint.port or 80, timeout=self.timeout
        )
        connection.sock = sock
        self._transport = sock
        return connection

    def request(self, method, path, payload, cancel):
        if method not in {"GET", "POST"} or path not in {"/api/tags", "/api/chat", "/api/version", "/api/ps"}:
            raise ValueError("unapproved local API route")
        if not self._lock.acquire(blocking=False):
            raise OllamaError("OLLAMA_BUSY")
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
                        try:
                            transport.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                    return

        watcher = threading.Thread(target=interrupt, daemon=True)
        response = None
        try:
            if self._closed or cancel.is_set():
                raise Cancelled()
            watcher.start()
            self._active = self._connection()
            if cancel.is_set() or self._closed:
                raise Cancelled()
            if expired.is_set():
                raise OllamaError("OLLAMA_TIMEOUT")
            body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
            if body and len(body) > 128 * 1024:
                raise OllamaError("OLLAMA_REQUEST_LIMIT")
            self._active.request(method, path, body=body, headers={"Content-Type": "application/json"})
            response = self._active.getresponse()
            if response.status != 200:
                code = {404: "OLLAMA_MODEL_MISSING", 503: "OLLAMA_OVERLOADED"}.get(
                    response.status, "OLLAMA_HTTP_ERROR"
                )
                raise OllamaError(code)
            data = response.read(self.max_response + 1)
            if len(data) > self.max_response:
                raise OllamaError("OLLAMA_RESPONSE_LIMIT")
            if cancel.is_set():
                raise Cancelled()
            if expired.is_set():
                raise OllamaError("OLLAMA_TIMEOUT")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise OllamaError("OLLAMA_MALFORMED_RESPONSE")
            return result
        except (socket.timeout, TimeoutError) as exc:
            if cancel.is_set():
                raise Cancelled() from exc
            raise OllamaError("OLLAMA_TIMEOUT") from exc
        except (OSError, http.client.HTTPException, ValueError, json.JSONDecodeError) as exc:
            if cancel.is_set():
                raise Cancelled() from exc
            if expired.is_set():
                raise OllamaError("OLLAMA_TIMEOUT") from exc
            raise OllamaError("OLLAMA_UNAVAILABLE_OR_MALFORMED") from exc
        finally:
            done.set()
            if response:
                response.close()
            if self._active:
                self._active.close()
            self._active = None
            self._transport = None
            if watcher.ident:
                watcher.join(timeout=.2)
            self._lock.release()

    def model_identity(self, cancel):
        data = self.request("GET", "/api/tags", None, cancel)
        if not isinstance(data.get("models"), list):
            raise OllamaError("OLLAMA_MALFORMED_RESPONSE")
        matches = [
            item
            for item in data["models"]
            if isinstance(item, dict) and item.get("name") == self.model
        ]
        if len(matches) != 1:
            raise OllamaError("OLLAMA_MODEL_MISSING")
        digest = matches[0].get("digest", "")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise OllamaError("OLLAMA_MODEL_DIGEST_INVALID")
        return {"model": self.model, "digest": digest}

    @staticmethod
    def _validate_messages(messages: Sequence[Mapping[str, object]]) -> list[dict[str, str]]:
        if not isinstance(messages, (list, tuple)) or not 1 <= len(messages) <= 20:
            raise ValueError("bounded chat messages required")
        validated: list[dict[str, str]] = []
        for item in messages:
            if not isinstance(item, Mapping) or set(item) != {"role", "content"}:
                raise ValueError("invalid chat message")
            role, content = item["role"], item["content"]
            if role not in {"system", "user", "assistant"} or not isinstance(content, str):
                raise ValueError("invalid chat message")
            if not content.strip() or len(content) > 16384:
                raise ValueError("chat message exceeds bounds")
            validated.append({"role": str(role), "content": content})
        return validated

    @staticmethod
    def _validate_tools(tools: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
        if not isinstance(tools, (list, tuple)) or not 1 <= len(tools) <= 12:
            raise ValueError("bounded tools required")
        encoded = json.dumps(tools, allow_nan=False)
        if len(encoded) > 32768:
            raise ValueError("tool schema exceeds bounds")
        validated: list[dict[str, object]] = []
        names: set[str] = set()
        for item in tools:
            if not isinstance(item, Mapping) or set(item) != {"type", "function"} or item.get("type") != "function":
                raise ValueError("invalid tool schema")
            function = item.get("function")
            if not isinstance(function, Mapping):
                raise ValueError("invalid tool schema")
            name = function.get("name")
            if not isinstance(name, str) or not name or len(name) > 64 or name in names:
                raise ValueError("invalid tool name")
            if set(function) - {"name", "description", "parameters"}:
                raise ValueError("invalid tool schema fields")
            if not isinstance(function.get("description"), str) or not isinstance(function.get("parameters"), Mapping):
                raise ValueError("invalid tool schema")
            names.add(name)
            validated.append(dict(item))
        return validated

    def _chat_payload(
        self,
        messages,
        *,
        structured: bool,
        tools: Sequence[Mapping[str, object]] | None = None,
        think: bool = False,
        keep_alive: str | int | None = None,
    ):
        payload: dict[str, object] = {
            "model": self.model,
            "messages": self._validate_messages(messages),
            "stream": False,
            "think": bool(think),
            "keep_alive": self.config.keep_alive if keep_alive is None else keep_alive,
            "options": {
                "num_ctx": self.config.context_tokens,
                "num_predict": self.config.max_output_tokens,
                "temperature": 0,
            },
        }
        if structured:
            payload["format"] = "json"
        if tools is not None:
            payload["tools"] = self._validate_tools(tools)
        return payload

    @staticmethod
    def _validate_tool_calls(message: Mapping[str, object]) -> list[dict[str, object]]:
        raw = message.get("tool_calls", [])
        if raw in (None, []):
            return []
        if not isinstance(raw, list) or not 1 <= len(raw) <= 4:
            raise OllamaError("OLLAMA_TOOL_CALLS_INVALID")
        result: list[dict[str, object]] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise OllamaError("OLLAMA_TOOL_CALLS_INVALID")
            function = item.get("function")
            if not isinstance(function, Mapping):
                raise OllamaError("OLLAMA_TOOL_CALLS_INVALID")
            name = function.get("name")
            arguments = function.get("arguments", {})
            if not isinstance(name, str) or not name or len(name) > 64 or not isinstance(arguments, Mapping):
                raise OllamaError("OLLAMA_TOOL_CALLS_INVALID")
            if len(json.dumps(arguments, allow_nan=False)) > 8192:
                raise OllamaError("OLLAMA_TOOL_CALLS_INVALID")
            result.append({"function": {"name": name, "arguments": dict(arguments)}})
        return result

    def chat_message(
        self,
        messages,
        cancel,
        *,
        tools: Sequence[Mapping[str, object]] | None = None,
        think: bool = False,
        keep_alive: str | int | None = None,
    ) -> dict[str, object]:
        data = self.request(
            "POST",
            "/api/chat",
            self._chat_payload(
                messages,
                structured=False,
                tools=tools,
                think=think,
                keep_alive=keep_alive,
            ),
            cancel,
        )
        if data.get("model") != self.model or data.get("done") is not True:
            raise OllamaError("OLLAMA_MODEL_OR_COMPLETION_MISMATCH")
        message = data.get("message")
        if not isinstance(message, Mapping):
            raise OllamaError("OLLAMA_MALFORMED_RESPONSE")
        content = message.get("content", "")
        if not isinstance(content, str) or len(content) > 32768:
            raise OllamaError("OLLAMA_MALFORMED_RESPONSE")
        tool_calls = self._validate_tool_calls(message)
        if not content.strip() and not tool_calls:
            raise OllamaError("OLLAMA_MALFORMED_RESPONSE")
        result: dict[str, object] = {
            "content": content,
            "tool_calls": tool_calls,
            "model": self.model,
        }
        for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration", "prompt_eval_count", "eval_count"):
            value = data.get(key)
            if isinstance(value, int) and value >= 0:
                result[key] = value
        return result

    def _chat_result(self, messages, cancel, *, structured):
        data = self.request(
            "POST", "/api/chat", self._chat_payload(messages, structured=structured), cancel
        )
        if data.get("model") != self.model or data.get("done") is not True:
            raise OllamaError("OLLAMA_MODEL_OR_COMPLETION_MISMATCH")
        if not isinstance(data.get("message"), dict):
            raise OllamaError("OLLAMA_MALFORMED_RESPONSE")
        content = data["message"].get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("OLLAMA_MALFORMED_RESPONSE")
        return content

    def chat(self, messages, cancel):
        return self._chat_result(messages, cancel, structured=True)

    def chat_text(self, messages, cancel):
        """Return normal spoken-conversation text with model thinking disabled."""
        return self._chat_result(messages, cancel, structured=False)

    def loaded_models(self, cancel) -> list[str]:
        data = self.request("GET", "/api/ps", None, cancel)
        models = data.get("models", [])
        if not isinstance(models, list):
            raise OllamaError("OLLAMA_MALFORMED_RESPONSE")
        result = []
        for item in models:
            if isinstance(item, Mapping) and isinstance(item.get("name"), str):
                result.append(str(item["name"]))
        return result

    def close(self):
        self._closed = True
        if self._transport:
            try:
                self._transport.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
