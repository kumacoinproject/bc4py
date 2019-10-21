from bc4py.config import P
from fastapi import HTTPException
from starlette.status import (
    HTTP_403_FORBIDDEN, HTTP_503_SERVICE_UNAVAILABLE, HTTP_301_MOVED_PERMANENTLY)
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Any
from json import dumps
from logging import getLogger


log = getLogger('bc4py')

local_address = {
    "localhost",
    "127.0.0.1",
}


class IndentResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=4,
            separators=(",", ":"),
        ).encode("utf-8")


class ConditionCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # check private method
        if request.url.path.startswith('/private'):
            if request.client.host in local_address:
                proxy_host = request.headers.get('X-Forwarded-For')
                if proxy_host is None or proxy_host in local_address:
                    pass  # success
                elif proxy_host.startswith('::ffff:') and proxy_host[7:] in local_address:
                    pass  # success (ipv6)
                else:
                    return PlainTextResponse(
                        "private method only allow from locals ({})".format(proxy_host),
                        status_code=HTTP_403_FORBIDDEN,
                    )
            else:
                return PlainTextResponse(
                    "private method only allow from locals",
                    status_code=HTTP_403_FORBIDDEN,
                )

        # redirect to doc page
        if request.url.path == '/' and request.method == 'GET':
            return PlainTextResponse(
                status_code=HTTP_301_MOVED_PERMANENTLY,
                headers={"Location": "./docs"},
            )

        # avoid API access until booting
        if P.F_NOW_BOOTING:
            return PlainTextResponse(
                "server is now on booting mode..",
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
            )

        # success
        return await call_next(request)


def error_response(errors=None):
    """simple error message response"""
    if errors is None:
        import traceback
        errors = str(traceback.format_exc())
    log.info(f"API error:\n{errors}")
    s = errors.split("\n")
    simple_msg = None
    while not simple_msg:
        simple_msg = s.pop(-1)
    return PlainTextResponse(simple_msg + '\n', 400)


__all__ = [
    "local_address",
    "IndentResponse",
    "ConditionCheckMiddleware",
    "error_response",
]
