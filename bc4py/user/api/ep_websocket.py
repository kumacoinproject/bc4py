from bc4py.config import P, stream
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.user import Accounting
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect
from logging import getLogger, INFO
from typing import List
import asyncio
import json

loop = asyncio.get_event_loop()
log = getLogger('bc4py')
getLogger('websockets').setLevel(INFO)

number = 0
clients: List['WsClient'] = list()
client_lock = asyncio.Lock()


CMD_NEW_BLOCK = 'Block'
CMD_NEW_TX = 'TX'
CMD_NEW_ACCOUNTING = 'Accounting'
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
            if ws.application_state == WebSocketState.DISCONNECTED:
                log.debug("websocket already closed")
                break
        except WebSocketDisconnect:
            log.debug("websocket disconnected")
            break
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
        if self.ws.application_state != WebSocketState.DISCONNECTED:
            await self.ws.close()
        async with client_lock:
            if self in clients:
                clients.remove(self)

    async def send(self, data: str):
        assert client_lock.locked()
        if self.ws.application_state == WebSocketState.DISCONNECTED:
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
                try:
                    await client.send(message)
                except Exception:
                    log.error("broadcast_clients exception", exc_info=True)


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
    elif isinstance(data, Accounting):
        data = {
            'txhash': None if getattr(data, 'txhash', None) is None else data.txhash.hex(),
            'balance': dict(data),
        }
        asyncio.ensure_future(broadcast_clients(CMD_NEW_ACCOUNTING, data, is_public=False))
    else:
        pass


# get new Block/TX object from reactive stream
stream.subscribe(on_next=websocket_reactive_stream, on_error=log.error)


__all__ = [
    "CMD_ERROR",
    "CMD_NEW_BLOCK",
    "CMD_NEW_TX",
    "CMD_NEW_ACCOUNTING",
    "websocket_route",
    "private_websocket_route",
    "broadcast_clients",
]
