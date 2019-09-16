from bc4py.config import P
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.status import (
    HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_503_SERVICE_UNAVAILABLE, HTTP_301_MOVED_PERMANENTLY)
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Any
from json import dumps
from logging import getLogger

log = getLogger('bc4py')
security = HTTPBasic()

username = 'username'
password = 'password'
localhost_urls = {
    "localhost",
    "127.0.0.1",
}


def setup_basic_auth_params(user: str, pwd: str, extra_locals=None):
    global username, password
    username = user
    password = pwd
    if extra_locals:
        localhost_urls.update(extra_locals)


def auth(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    """
    private method access allow only from local
    proxy is on local and add X-Forwarded-Host header
    """
    if request.client.host in localhost_urls:
        proxy_host = request.headers.get('X-Forwarded-Host')
        if proxy_host is None or proxy_host in localhost_urls:
            pass  # success
        else:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="1: private method only allow from locals",
            )
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="2: private method only allow from locals",
        )
    if credentials.username != username or credentials.password != password:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials


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
        if request.url.path == '/' and request.method == 'GET':
            return PlainTextResponse(
                status_code=HTTP_301_MOVED_PERMANENTLY,
                headers={"Location": "./docs"},
            )
        if P.F_NOW_BOOTING:
            return PlainTextResponse(
                "server is now on booting mode..",
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
            )
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
    "setup_basic_auth_params",
    "auth",
    "IndentResponse",
    "ConditionCheckMiddleware",
    "error_response",
]
