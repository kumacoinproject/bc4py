from bc4py.config import P, stream
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from starlette.websockets import WebSocket, WebSocketState
from logging import getLogger
from typing import List
import asyncio
import json

loop = asyncio.get_event_loop()
log = getLogger('bc4py')
number = 0
clients: List['WsClient'] = list()
client_lock = asyncio.Lock()


CMD_NEW_BLOCK = 'Block'
CMD_NEW_TX = 'TX'
CMD_ERROR = 'Error'


async def websocket_route(ws: WebSocket, is_public=True):
    """
    websocket public stream
    """
    await ws.accept()
    async with client_lock:
        clients.append(WsClient(ws, is_public))
    while not P.F_STOP:
        try:
            item = await asyncio.wait_for(ws.receive_json(), 0.2)
            # receive command
            # warning: not implemented, no function
            data = {
                'connect': len(clients),
                'is_public': is_public,
                'echo': item,
            }
            await ws.send_text(get_json_format(cmd='debug', data=data))
        except (asyncio.TimeoutError, TypeError):
            if ws.client_state == WebSocketState.DISCONNECTED:
                log.debug("websocket already closed")
                return
        except Exception:
            log.error('websocket_route exception', exc_info=True)
            break
    await ws.close()
    log.debug("close {}".format(ws))


async def private_websocket_route(ws: WebSocket):
    """
    websocket private stream
    """
    await websocket_route(ws, False)


class WsClient(object):

    def __init__(self, ws: WebSocket, is_public: bool):
        global number
        number += 1
        self.number = number
        self.ws = ws
        self.is_public = is_public

    def __repr__(self):
        ws_type = 'Pub' if self.is_public else 'Pri'
        return f"<WsClient {self.number} {ws_type} {self.ws.client.host}>"

    async def close(self):
        if self.ws.client_state != WebSocketState.DISCONNECTED:
            await self.ws.close()
        async with client_lock:
            if self in clients:
                clients.remove(self)

    async def send(self, data: str):
        assert client_lock.locked()
        if self.ws.client_state == WebSocketState.DISCONNECTED:
            clients.remove(self)
        else:
            await self.ws.send_text(data)


def get_json_format(cmd, data, status=True):
    send_data = {
        'cmd': cmd,
        'data': data,
        'status': status,
    }
    return json.dumps(send_data)


async def broadcast_clients(cmd, data, status=True, is_public=False):
    """broadcast to all clients"""
    message = get_json_format(cmd=cmd, data=data, status=status)
    async with client_lock:
        for client in clients:
            if is_public or not client.is_public:
                await client.send(message)


def websocket_reactive_stream(data):
    """receive Block/TX data from stream"""
    if P.F_STOP:
        pass
    elif P.F_NOW_BOOTING:
        pass
    elif isinstance(data, Block):
        asyncio.ensure_future(broadcast_clients(CMD_NEW_BLOCK, data.getinfo(), is_public=True))
    elif isinstance(data, TX):
        asyncio.ensure_future(broadcast_clients(CMD_NEW_TX, data.getinfo(), is_public=True))
    else:
        pass


# get new Block/TX object from reactive stream
stream.subscribe(on_next=websocket_reactive_stream, on_error=log.error)


__all__ = [
    "CMD_ERROR",
    "CMD_NEW_BLOCK",
    "CMD_NEW_TX",
    "websocket_route",
    "private_websocket_route",
    "broadcast_clients",
]
