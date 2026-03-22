from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any

from mitmproxy import eventsequence, http
from mitmproxy.options import Options
from mitmproxy.proxy.layers import http as http_layers
from mitmproxy.test import taddons, tflow

from proxylens_mitmproxy.addon import ProxyLens

type FlowHandler = Callable[[http.HTTPFlow], None]
_HANDLER_EXCEPTION_KEY = "proxylens_responder_exception"


class ResponderAddon:
    __test__ = False

    def __init__(self, handler: FlowHandler) -> None:
        self._handler = handler

    def request(self, flow: http.HTTPFlow) -> None:
        try:
            self._handler(flow)
        except Exception as exc:
            flow.metadata[_HANDLER_EXCEPTION_KEY] = exc
            raise


class TestMitmProxy:
    __test__ = False

    def __init__(
        self,
        proxy_lens: ProxyLens,
        handler: FlowHandler,
        *,
        options: Options | None = None,
    ) -> None:
        self._proxy_lens = proxy_lens
        self._responder = ResponderAddon(handler)
        self._context = taddons.context(
            proxy_lens,
            self._responder,
            options=options,
        )
        self._entered = False

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | str = b"",
        headers: Mapping[str, str | bytes] | None = None,
    ) -> http.HTTPFlow:
        request = http.Request.make(method, url, content=content, headers=headers or {})
        return self.send(request)

    def send(self, request: http.Request) -> http.HTTPFlow:
        self._ensure_entered()
        loop = self._context.master.event_loop
        return loop.run_until_complete(self.asend(request))

    async def arequest(
        self,
        method: str,
        url: str,
        *,
        content: bytes | str = b"",
        headers: Mapping[str, str | bytes] | None = None,
    ) -> http.HTTPFlow:
        request = http.Request.make(method, url, content=content, headers=headers or {})
        return await self.asend(request)

    async def asend(self, request: http.Request) -> http.HTTPFlow:
        self._ensure_entered()
        flow = tflow.tflow(req=request, resp=False, ws=False)
        await self._drive_flow(flow)
        return flow

    def close(self) -> None:
        if not self._entered:
            return
        self._context.__exit__(None, None, None)
        self._entered = False

    async def aclose(self) -> None:
        self.close()

    def __enter__(self) -> TestMitmProxy:
        self._ensure_entered()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    async def __aenter__(self) -> TestMitmProxy:
        self._ensure_entered()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.aclose()

    async def _drive_flow(self, flow: http.HTTPFlow) -> None:
        for event in eventsequence.iterate(flow):
            await self._context.master.addons.handle_lifecycle(event)
            if flow.metadata.get(_HANDLER_EXCEPTION_KEY):
                raise flow.metadata[_HANDLER_EXCEPTION_KEY]
            if isinstance(event, http_layers.HttpRequestHeadersHook):
                self._apply_streaming(flow.request)
            elif (
                isinstance(event, http_layers.HttpResponseHeadersHook) and flow.response
            ):
                self._apply_streaming(flow.response)

    def _ensure_entered(self) -> None:
        if self._entered:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if (
            loop is not None
            and loop.is_running()
            and self._context.master.event_loop is not loop
        ):
            raise RuntimeError("TestMitmProxy was created for a different event loop")
        self._context.__enter__()
        self._entered = True

    def _apply_streaming(self, message: http.Message) -> None:
        if not callable(message.stream):
            return
        raw_content = message.raw_content
        if raw_content is None:
            return
        for chunk in _chunk_bytes(raw_content):
            message.stream(chunk)
        message.stream(b"")
        message.data.content = None


def _chunk_bytes(data: bytes, *, chunk_size: int = 4) -> list[bytes]:
    if not data:
        return []
    return [
        data[index : index + chunk_size] for index in range(0, len(data), chunk_size)
    ]
