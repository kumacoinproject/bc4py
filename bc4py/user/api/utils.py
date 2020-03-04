from bc4py.config import P
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
    "127.0.0.1",
    "::1",
}
ALLOW_CROSS_ORIGIN_ACCESS = {
    'Access-Control-Allow-Origin': '*'
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
                    pass  # success (IPv6 address including IPv4 address)
                else:
                    return PlainTextResponse(
                        "1 private method only allow from locals ({})".format(proxy_host),
                        status_code=HTTP_403_FORBIDDEN,
                        headers=ALLOW_CROSS_ORIGIN_ACCESS,
                    )
            else:
                return PlainTextResponse(
                    "2 private method only allow from locals ({})".format(request.client.host),
                    status_code=HTTP_403_FORBIDDEN,
                    headers=ALLOW_CROSS_ORIGIN_ACCESS,
                )

        # redirect to doc page
        if request.url.path == '/' and request.method == 'GET':
            return PlainTextResponse(
                status_code=HTTP_301_MOVED_PERMANENTLY,
                headers={"Location": "./docs"},
            )

        # avoid API access until booting
        if P.F_NOW_BOOTING and request.url.path != '/public/getsysteminfo':
            return PlainTextResponse(
                "server is now on booting mode..",
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                headers=ALLOW_CROSS_ORIGIN_ACCESS,
            )

        # success
        return await call_next(request)


def error_response(errors=None):
    """simple error message response"""
    if errors is None:
        import traceback
        errors = str(traceback.format_exc())
    log.debug(f"API error:\n{errors}")
    s = errors.split("\n")
    simple_msg = None
    while not simple_msg:
        simple_msg = s.pop(-1)
    return PlainTextResponse(
        simple_msg + '\n',
        status_code=400,
        headers=ALLOW_CROSS_ORIGIN_ACCESS,
    )


__all__ = [
    "local_address",
    "IndentResponse",
    "ConditionCheckMiddleware",
    "error_response",
]
