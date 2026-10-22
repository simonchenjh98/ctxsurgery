from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import pytest

from ctxsurgery.providers import OpenAICompatibleRunner, ProviderError, validate_base_url


@contextmanager
def server(*, status=200, body=None, redirect=False, delay=0, responder=None):
    state = {"requests": []}
    encoded = body if isinstance(body, bytes) else json.dumps(
        body if body is not None else {
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14},
        }
    ).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state["requests"].append({
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
            })
            if delay:
                time.sleep(delay)
            response_body = encoded
            if responder is not None:
                response_body = json.dumps(responder(state["requests"][-1]["body"])).encode()
            self.send_response(status)
            if redirect:
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/stolen")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            try:
                self.wfile.write(response_body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def log_message(self, *_args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}/v1", state
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=1)


@pytest.mark.parametrize("url", [
    "http://example.com/v1", "http://localhost.evil/v1", "ftp://127.0.0.1/v1",
    "https://user:password@example.com/v1", "https://example.com/v1?secret=a",
    "https://example.com/v1#frag", "https://example.com/v1?", "https://example.com:0/v1",
    "https://example.com:99999/v1", "https://example.com/\\evil", "https://example.com/\n",
    "https:///v1", "", "http://2130706433/v1",
])
def test_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


@pytest.mark.parametrize("url", ["http://localhost:123/v1", "http://127.0.0.1/v1", "http://[::1]/v1"])
def test_accepts_loopback_http(url):
    assert validate_base_url(url)[1] is True


def test_remote_requires_key_and_secret_is_not_in_repr():
    with pytest.raises(ValueError, match="environment variable"):
        OpenAICompatibleRunner("test")
    runner = OpenAICompatibleRunner("test", api_key="secret-123")
    assert "secret-123" not in repr(runner)


@pytest.mark.parametrize("kwargs", [
    {"timeout": 0}, {"timeout": float("nan")}, {"timeout": 601}, {"timeout": True},
    {"max_output_tokens": 0}, {"max_output_tokens": True}, {"model": ""},
    {"api_key": "bad\nsecret"},
])
def test_invalid_options(kwargs):
    options = {"model": "test", "base_url": "http://localhost/v1"}
    options.update(kwargs)
    with pytest.raises(ValueError):
        OpenAICompatibleRunner(**options)


@pytest.mark.parametrize("effort", ["", "none", "LOW", "minimal", "xhigh", True, 1, [], {}])
def test_rejects_invalid_reasoning_effort(effort):
    with pytest.raises(ValueError, match="Reasoning effort"):
        OpenAICompatibleRunner("test", "http://localhost/v1", reasoning_effort=effort)


@pytest.mark.parametrize("effort", [None, "low", "medium", "high"])
def test_reasoning_effort_is_optional_and_forwarded(effort):
    with server() as (url, state):
        OpenAICompatibleRunner("test", url, reasoning_effort=effort)("context", "task")
    body = state["requests"][0]["body"]
    expected = {
        "model": "test",
        "messages": [
            {"role": "system", "content": "context"},
            {"role": "user", "content": "task"},
        ],
        "temperature": 0,
        "max_tokens": 1024,
        "stream": False,
    }
    if effort is not None:
        expected["reasoning_effort"] = effort
    assert body == expected


@pytest.mark.parametrize("code", ["PRIVATE", "http_099", "http_600", "http_429\nPRIVATE", None, 429, []])
def test_error_code_rejects_unknown_or_unsafe_values(code):
    with pytest.raises(ValueError, match="Invalid provider error code") as captured:
        ProviderError("sanitized message", code=code)
    assert "PRIVATE" not in str(captured.value)


def test_provider_error_default_code_preserves_existing_constructor():
    error = ProviderError("sanitized message")
    assert str(error) == "sanitized message"
    assert error.code == "provider_error"


def test_request_and_usage_are_correct():
    with server() as (url, state):
        runner = OpenAICompatibleRunner("local-test", url, "a-test-key")
        response = runner("上下文", "task")
    assert response.output == "hello"
    assert response.usage == {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14}
    assert len(state["requests"]) == 1
    request = state["requests"][0]
    assert request["path"] == "/v1/chat/completions"
    assert request["authorization"] == "Bearer a-test-key"
    assert request["body"]["messages"] == [
        {"role": "system", "content": "上下文"}, {"role": "user", "content": "task"}
    ]


def test_loopback_can_omit_key():
    with server() as (url, state):
        OpenAICompatibleRunner("test", url)("context", "task")
    assert state["requests"][0]["authorization"] is None


@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_errors_never_echo_body_and_never_retry(status):
    with server(status=status, body=b"PRIVATE CONTEXT API_KEY") as (url, state):
        with pytest.raises(ProviderError) as captured:
            OpenAICompatibleRunner("test", url)("context", "task")
    assert str(status) in str(captured.value)
    assert "PRIVATE" not in str(captured.value)
    assert "API_KEY" not in str(captured.value)
    assert captured.value.code == f"http_{status}"
    assert len(state["requests"]) == 1


def test_redirect_does_not_forward_credentials():
    with server(status=307, redirect=True) as (url, state):
        with pytest.raises(ProviderError, match="redirect refused") as captured:
            OpenAICompatibleRunner("test", url, "secret")("context", "task")
    assert captured.value.code == "redirect_refused"
    assert len(state["requests"]) == 1


@pytest.mark.parametrize("body", [b"PRIVATE invalid JSON", {}, [], {"choices": []}, {"choices": [{"message": {"content": None}}]}])
def test_invalid_responses_are_sanitized(body):
    with server(body=body) as (url, _):
        with pytest.raises(ProviderError, match="not a supported") as captured:
            OpenAICompatibleRunner("test", url)("context", "task")
    assert "PRIVATE" not in str(captured.value)
    assert captured.value.code == "invalid_response"


def test_usage_whitelist_rejects_secrets_and_invalid_counts():
    with server(body={
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": True, "completion_tokens": -1, "total_tokens": 3, "secret": "PRIVATE"},
    }) as (url, _):
        response = OpenAICompatibleRunner("test", url)("context", "task")
    assert response.usage == {"total_tokens": 3}


@pytest.mark.parametrize("content", ["", "a superficially correct but truncated answer"])
def test_truncated_completion_is_an_error_not_task_evidence(content):
    with server(body={
        "choices": [{"finish_reason": "length", "message": {"content": content}}],
        "usage": {"completion_tokens": 4096},
    }) as (url, state):
        with pytest.raises(ProviderError, match="output token limit") as captured:
            OpenAICompatibleRunner("test", url)("context", "task")
    assert captured.value.code == "output_limit"
    assert len(state["requests"]) == 1


def test_oversize_request_makes_no_call():
    with server() as (url, state):
        with pytest.raises(ProviderError, match="Request exceeds") as captured:
            OpenAICompatibleRunner("test", url)("x" * (2 * 1024 * 1024), "task")
    assert captured.value.code == "request_limit"
    assert not state["requests"]


def test_oversize_response_is_rejected():
    with server(body=b"x" * (4 * 1024 * 1024 + 1)) as (url, _):
        with pytest.raises(ProviderError, match="response exceeds") as captured:
            OpenAICompatibleRunner("test", url)("context", "task")
    assert captured.value.code == "response_limit"


def test_timeout_is_sanitized():
    with server(delay=0.2) as (url, _):
        with pytest.raises(ProviderError, match="timed out") as captured:
            OpenAICompatibleRunner("test", url, timeout=0.01)("PRIVATE", "task")
    assert captured.value.code == "connection_failed"


def test_invalid_unicode_is_sanitized():
    with server() as (url, state):
        with pytest.raises(ProviderError, match="unsupported text") as captured:
            OpenAICompatibleRunner("test", url)("\ud800", "task")
    assert captured.value.code == "invalid_request"
    assert not state["requests"]


@pytest.mark.parametrize("effort", [None, "low", "medium", "high"])
def test_cli_diagnosis_through_real_loopback_http(tmp_path, monkeypatch, effort):
    from ctxsurgery.cli import main
    from ctxsurgery.demo import demo_case, synthetic_runner

    # This is a real HTTP integration test against a synthetic config executor,
    # not a claim to have measured a live LLM.
    def responder(payload):
        return {"choices": [{"message": {"content": synthetic_runner(
            payload["messages"][0]["content"], payload["messages"][1]["content"]
        )}}]}

    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(demo_case().to_dict()), encoding="utf-8")
    monkeypatch.delenv("CTXSURGERY_TEST_KEY", raising=False)
    with server(responder=responder) as (url, state):
        arguments = [
            "diagnose", str(case_path), "--provider", "openai", "--model", "test-config-interpreter",
            "--base-url", url, "--api-key-env", "CTXSURGERY_TEST_KEY", "--out", str(tmp_path / "report"),
            "--repeats", "1",
        ]
        if effort is not None:
            arguments.extend(["--reasoning-effort", effort])
        code = main(arguments)
    assert code == 0
    result = json.loads((tmp_path / "report" / "report.json").read_text(encoding="utf-8"))
    assert result["status"] == "localized"
    assert set(result["repair_ids"]) == {"ci-gate", "approval-gate"}
    assert result["calls_used"] == len(state["requests"])
    assert result["run"]["model"] == "test-config-interpreter"
    assert all(request["authorization"] is None for request in state["requests"])
    if effort is None:
        assert "reasoning_effort" not in result["run"]
        assert all("reasoning_effort" not in request["body"] for request in state["requests"])
    else:
        assert result["run"]["reasoning_effort"] == effort
        assert all(request["body"]["reasoning_effort"] == effort for request in state["requests"])


def test_cli_runner_failure_saves_evidence_and_exits_three(tmp_path, monkeypatch):
    from ctxsurgery.cli import main
    from ctxsurgery.demo import demo_case

    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(demo_case().to_dict()), encoding="utf-8")
    monkeypatch.delenv("CTXSURGERY_TEST_KEY", raising=False)
    with server(status=500, body=b"PRIVATE") as (url, state):
        code = main([
            "diagnose", str(case_path), "--provider", "openai", "--model", "test",
            "--base-url", url, "--api-key-env", "CTXSURGERY_TEST_KEY", "--out", str(tmp_path / "report"),
            "--repeats", "1",
        ])
    assert code == 3
    encoded = (tmp_path / "report" / "report.json").read_text(encoding="utf-8")
    assert "PRIVATE" not in encoded
    result = json.loads(encoded)
    assert result["status"] == "runner_error"
    assert result["calls_used"] == len(state["requests"]) == 1
    assert result["experiments"][0]["trials"][0]["passed"] is None
