from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen

import pytest
from mitmproxy import http

from proxylens_mitmproxy import ProxyLens, TestMitmProxy

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SERVER_DIR = _REPO_ROOT / "server"


def test_addon_http_client_integrates_with_real_server(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "server-data"
    with _run_server(data_dir=data_dir) as server:
        monkeypatch.setenv("PROXYLENS_SERVER_BASE_URL", server["base_url"])
        addon = ProxyLens(
            node_name="proxy-a",
            trace_id_generator=lambda: "01K0TRACEPROXYAEXAMPLE0000",
            request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
            blob_id_generator=_blob_ids(),
        )

        def handler(flow: http.HTTPFlow) -> None:
            flow.response = http.Response.make(
                201,
                b'{"status":"created"}',
                {"content-type": "application/json"},
            )

        with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
            flow = proxy.request(
                "POST",
                "https://example.test/widgets",
                content=b'{"name":"demo"}',
                headers={"content-type": "application/json"},
            )

        request_id = flow.request.headers["X-ProxyLens-RequestId"]
        request_detail = _get_json(f"{server['base_url']}/requests/{request_id}")
        request_events = _get_json(f"{server['base_url']}/requests/{request_id}/events")
        request_body = _get_bytes(f"{server['base_url']}/requests/{request_id}/body")
        response_body = _get_bytes(
            f"{server['base_url']}/requests/{request_id}/response/body"
        )

    assert request_detail["request_id"] == "01K0REQUESTPROXYAEXAMPLE00"
    assert request_detail["trace_id"] == "01K0TRACEPROXYAEXAMPLE0000"
    assert request_detail["node_name"] == "proxy-a"
    assert request_detail["request_method"] == "POST"
    assert request_detail["response_status_code"] == 201
    assert request_detail["request_body_size"] == 15
    assert request_detail["response_body_size"] == 20
    assert [persisted["event"]["type"] for persisted in request_events] == [
        "http_request_started",
        "http_request_body",
        "http_request_completed",
        "http_response_started",
        "http_response_body",
        "http_response_completed",
    ]
    assert request_body == b'{"name":"demo"}'
    assert response_body == b'{"status":"created"}'


@contextmanager
def _run_server(*, data_dir: Path):
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env["PROXYLENS_SERVER_DATA_DIR"] = str(data_dir)
    process = subprocess.Popen(
        [
            str(_SERVER_DIR / ".venv/bin/python"),
            "-m",
            "uvicorn",
            "proxylens_server.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=_SERVER_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_server(base_url, process)
        yield {"base_url": base_url, "process": process}
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _wait_for_server(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 20
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise AssertionError(f"server exited early:\n{output}")
        try:
            with urlopen(f"{base_url}/openapi.json", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    output = process.stdout.read() if process.stdout else ""
    raise AssertionError(f"server did not become ready in time:\n{output}")


def _get_json(url: str) -> object:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_bytes(url: str) -> bytes:
    with urlopen(url, timeout=5) as response:
        return response.read()


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _blob_ids():
    counter = 0

    def make() -> str:
        nonlocal counter
        counter += 1
        return f"01K0BLOB{counter:018d}"

    return make
