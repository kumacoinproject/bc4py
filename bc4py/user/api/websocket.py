from bc4py.config import P, stream
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from aiohttp.web_ws import WebSocketResponse
from aiohttp import web
from logging import getLogger
from typing import List
import asyncio
import json

loop = asyncio.get_event_loop()
log = getLogger('bc4py')
number = 0
clients: List['WsClient'] = list()

CMD_NEW_BLOCK = 'Block'
CMD_NEW_TX = 'TX'
CMD_ERROR = 'Error'


# TODO: fix error: "socket.send() raised exception"
#  => https://github.com/aio-libs/aiohttp/issues/3448
async def websocket_route(request: web.BaseRequest):
    if request.rel_url.path.startswith('/public/'):
        is_public = True
    elif request.rel_url.path.startswith('/private/'):
        is_public = False
    else:
        raise web.HTTPNotFound()
    client = await websocket_protocol_check(request=request, is_public=is_public)
    while not P.F_STOP:
        try:
            item = await client.ws.receive_json(timeout=1.0)
            # receive command
            # warning: not implemented, no function
            data = {
                'connect': len(clients),
                'is_public': client.is_public,
                'echo': item,
            }
            await client.send(get_json_format(cmd='debug', data=data))
        except (asyncio.TimeoutError, TypeError):
            if client.ws.closed:
                log.debug("websocket already closed")
                break
        except Exception:
            log.error('websocket_route exception', exc_info=True)
            break
    await client.close()
    log.debug("close {}".format(client))


class WsClient(object):

    def __init__(self, ws, request, is_public):
        global number
        number += 1
        self.number = number
        self.ws: WebSocketResponse = ws
        self.request = request
        self.is_public = is_public
        clients.append(self)

    def __repr__(self):
        ws_type = 'Pub' if self.is_public else 'Pri'
        return f"<WsClient {self.number} {ws_type} {self.request.remote}>"

    async def close(self):
        if not self.ws.closed:
            await self.ws.close()
        if self in clients:
            clients.remove(self)

    async def send(self, data: str):
        if self.ws.closed:
            clients.remove(self)
        else:
            await self.ws.send_str(data)


async def websocket_protocol_check(request, is_public):
    """upgrade to WebSocket protocol"""
    ws = web.WebSocketResponse()
    ws.enable_compression()
    available = ws.can_prepare(request)
    if not available:
        log.debug(f"cannot prepare websocket {request.remote}")
        raise web.HTTPInternalServerError()
    await ws.prepare(request)
    log.debug(f"protocol upgrade to websocket {request.remote}")
    return WsClient(ws, request, is_public)


def get_json_format(cmd, data, status=True):
    send_data = {
        'cmd': cmd,
        'data': data,
        'status': status,
    }
    return json.dumps(send_data)


def broadcast_clients(cmd, data, status=True, is_public=False):
    """broadcast to all clients"""
    message = get_json_format(cmd=cmd, data=data, status=status)
    for client in clients:
        if is_public or not client.is_public:
            loop.call_soon(client.send, message)


async def websocket_reactive_stream():
    while not P.F_STOP:
        try:
            data = await asyncio.wait_for(stream, 1.0)
            if P.F_NOW_BOOTING:
                pass
            elif isinstance(data, Block):
                broadcast_clients(cmd=CMD_NEW_BLOCK, data=data.getinfo(), is_public=True)
            elif isinstance(data, TX):
                broadcast_clients(cmd=CMD_NEW_TX, data=data.getinfo(), is_public=True)
            else:
                pass
        except asyncio.TimeoutError:
            pass
        except Exception:
            log.error("websocket_stream exception", exc_info=True)
    log.info("close websocket reactive stream")


# get new Block/TX object from reactive stream
asyncio.ensure_future(websocket_reactive_stream())


__all__ = [
    "CMD_ERROR",
    "CMD_NEW_BLOCK",
    "CMD_NEW_TX",
    "websocket_route",
    "broadcast_clients",
]
