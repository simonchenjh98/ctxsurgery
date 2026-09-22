"""Small, bounded OpenAI-compatible chat-completions adapter.

No automatic retries or redirects: each call is exactly one experiment trial.
Errors intentionally exclude HTTP bodies, headers, and exception details.
"""

from __future__ import annotations

import ipaddress
import http.client
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field


class ProviderError(RuntimeError):
    """A sanitized remote-runner error safe to include in a report."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_base_url(base_url: str) -> tuple[str, bool]:
    """Return a normalized URL and whether its host is loopback.

    Plain HTTP is permitted only for local model servers. HTTPS endpoints
    are explicitly selected by the caller; this is not an SSRF sandbox.
    """
    if not isinstance(base_url, str) or not base_url or any(
        ord(char) < 33 or ord(char) == 127 for char in base_url
    ):
        raise ValueError("Base URL must be a URL without whitespace or control characters.")
    try:
        parsed = urllib.parse.urlsplit(base_url)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid base URL.") from None
    if (
        parsed.scheme not in ("https", "http")
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "?" in base_url
        or "#" in base_url
        or "\\" in base_url
        or port == 0
    ):
        raise ValueError("Use an HTTP(S) base URL without credentials, query, or fragment.")
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host.lower() == "localhost"
    if parsed.scheme == "http" and not loopback:
        raise ValueError("Plain HTTP is allowed only for loopback model servers.")
    return base_url.rstrip("/"), loopback


@dataclass
class OpenAICompatibleRunner:
    """Callable adapter sending context as system and task as user messages.

    A local compatible server can omit an API key. Remote endpoints require
    a key. API keys are omitted from repr, errors, and returned usage metadata.
    """

    model: str
    base_url: str = "https://api.openai.com/v1"
    api_key: str | None = field(default=None, repr=False)
    timeout: float = 30.0
    max_output_tokens: int = 1024
    _endpoint: str = field(init=False, repr=False)
    _opener: object = field(init=False, repr=False)

    def __post_init__(self):
        self.base_url, loopback = validate_base_url(self.base_url)
        if not isinstance(self.model, str) or not self.model.strip() or any(
            ord(char) < 32 for char in self.model
        ):
            raise ValueError("Model must be a nonempty string without control characters.")
        if not isinstance(self.timeout, (int, float)) or isinstance(self.timeout, bool) or not (
            math.isfinite(self.timeout) and 0 < self.timeout <= 600
        ):
            raise ValueError("Timeout must be between 0 and 600 seconds.")
        if type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= 131072:
            raise ValueError("Maximum output tokens must be an integer from 1 to 131072.")
        if self.api_key is not None and (
            not isinstance(self.api_key, str)
            or any(ord(char) < 33 or ord(char) > 126 for char in self.api_key)
        ):
            raise ValueError("API key contains invalid characters.")
        if not loopback and not self.api_key:
            raise ValueError("Remote endpoints require an API key in the selected environment variable.")
        self._endpoint = self.base_url + "/chat/completions"
        # Do not route loopback fixtures/model servers through environment proxies.
        handlers = [_NoRedirect()]
        if loopback:
            handlers.append(urllib.request.ProxyHandler({}))
        self._opener = urllib.request.build_opener(*handlers)

    def __call__(self, context: str, task: str):
        from .models import Response

        try:
            payload = json.dumps(
                {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": context},
                        {"role": "user", "content": task},
                    ],
                    "temperature": 0,
                    "max_tokens": self.max_output_tokens,
                    "stream": False,
                },
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        except (ValueError, TypeError, UnicodeError):
            raise ProviderError("Request contains unsupported text or JSON values.") from None
        if len(payload) > 2 * 1024 * 1024:
            raise ProviderError("Request exceeds the 2 MiB adapter limit.")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = urllib.request.Request(self._endpoint, data=payload, headers=headers, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if 300 <= code < 400:
                raise ProviderError("HTTP redirect refused; configure the final endpoint explicitly.") from None
            raise ProviderError(f"Provider returned HTTP {code}; response body omitted.") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, http.client.HTTPException):
            raise ProviderError("Provider connection failed or timed out; details omitted.") from None
        if len(raw) > 4 * 1024 * 1024:
            raise ProviderError("Provider response exceeds the 4 MiB adapter limit.")
        try:
            data = json.loads(raw)
            output = data["choices"][0]["message"]["content"]
            if not isinstance(output, str):
                raise TypeError
        except (ValueError, TypeError, KeyError, IndexError, UnicodeError):
            raise ProviderError("Provider response is not a supported chat-completions JSON response.") from None
        usage = data.get("usage")
        safe_usage = None
        if isinstance(usage, dict):
            safe_usage = {
                key: usage[key]
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if type(usage.get(key)) is int and usage[key] >= 0
            }
        return Response(output=output, usage=safe_usage)
