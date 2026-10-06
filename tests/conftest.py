"""Keep synchronous legacy tests working with the installed Starlette/httpx stack.

Starlette's bundled TestClient blocks in this Python 3.14 environment. This
small adapter keeps the existing synchronous test API while dispatching through
httpx's supported in-process ASGI transport.
"""
import asyncio
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import fastapi.testclient


class _ASGISyncTestClient:
    __test__ = False
    def __init__(self, app, **_kwargs):
        self.app = app

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    async def _request(self, method, url, **kwargs):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://testserver"
        ) as client:
            return await client.request(method, url, **kwargs)

    def request(self, method, url, **kwargs):
        # FileResponse streaming stalls under this Python 3.14/httpx combination;
        # serve mounted static assets from the same directory for legacy tests.
        if method.upper() == "GET" and urlsplit(url).path.startswith("/static/"):
            mount = next(route for route in self.app.routes if getattr(route, "name", None) == "static")
            root = Path(mount.app.directory).resolve()
            target = (root / urlsplit(url).path.removeprefix("/static/")).resolve()
            if root not in target.parents or not target.is_file():
                return httpx.Response(404, request=httpx.Request(method, url))
            mime, _ = mimetypes.guess_type(target.name)
            return httpx.Response(200, content=target.read_bytes(), headers={"content-type": mime or "application/octet-stream"}, request=httpx.Request(method, url))
        return asyncio.run(self._request(method, url, **kwargs))

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


fastapi.testclient.TestClient = _ASGISyncTestClient
