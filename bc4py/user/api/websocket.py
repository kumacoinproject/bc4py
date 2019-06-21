from bc4py.config import P, stream
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from aiohttp.web_ws import WebSocketResponse
from aiohttp import web
from logging import getLogger
import asyncio
import json

log = getLogger('bc4py')
number = 0
clients = list()
loop = asyncio.get_event_loop()

CMD_NEW_BLOCK = 'Block'
CMD_NEW_TX = 'TX'
CMD_ERROR = 'Error'


# TODO: fix error: "socket.send() raised exception" => https://github.com/aio-libs/aiohttp/issues/3448
async def websocket_route(request):
    if request.rel_url.path.startswith('/public/'):
        is_public = True
    elif request.rel_url.path.startswith('/private/'):
        is_public = False
    else:
        raise web.HTTPNotFound()
    client = await websocket_protocol_check(request=request, is_public=is_public)
    while True:
        try:
            msg = await client.ws.receive(timeout=5.0)
            if msg.type == web.WSMsgType.TEXT:
                log.debug("Get text from {} data={}".format(client, msg.data))
                # send dummy response
                data = {'connect': len(clients), 'is_public': client.is_public, 'echo': msg.data}
                await client.send(get_send_format(cmd='debug', data=data))
            elif msg.type == web.WSMsgType.BINARY:
                log.debug("Get bin from {} data={}".format(client, msg.data))
            elif msg.type == web.WSMsgType.CLOSED:
                log.debug("Get close signal from {} data={}".format(client, msg.data))
                break
            elif msg.type == web.WSMsgType.ERROR:
                log.error("Get error from {} data={}".format(client, msg.data))
        except asyncio.TimeoutError:
            if client.ws.closed:
                log.debug("websocket already closed")
                break
        except Exception as e:
            import traceback
            await client.send(
                raw_data=get_send_format(cmd=CMD_ERROR, data=str(traceback.format_exc()), status=False))
            break
    log.debug("close {}".format(client))
    try:
        if not client.ws.closed:
            await client.close()
    except Exception:
        pass


async def websocket_protocol_check(request, is_public):
    ws = web.WebSocketResponse()
    ws.enable_compression()
    available = ws.can_prepare(request)
    if not available:
        raise TypeError('Cannot prepare websocket')
    await ws.prepare(request)
    log.debug("protocol upgrade to websocket. {}".format(request.remote))
    return WsConnection(ws=ws, request=request, is_public=is_public)


class WsConnection(object):

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
        return f"<Websocket {self.number} {ws_type} {self.request.remote}>"

    async def close(self):
        await self.ws.close()
        if self in clients:
            clients.remove(self)

    async def send(self, raw_data):
        assert isinstance(raw_data, str)
        if self.ws.closed:
            clients.remove(self)
        else:
            await self.ws.send_str(raw_data)

    async def send_bytes(self, b):
        assert isinstance(b, bytes)
        if self.ws.closed:
            clients.remove(self)
        else:
            await self.ws.send_bytes(b)


def get_send_format(cmd, data, status=True):
    send_data = {
        'cmd': cmd,
        'data': data,
        'status': status,
    }
    return json.dumps(send_data)


def send_websocket_data(cmd, data, status=True, is_public_data=False):

    async def exe():
        for client in clients.copy():
            try:
                if is_public_data or not client.is_public:
                    await client.send(send_format)
            except Exception:
                pass

    if P.F_NOW_BOOTING:
        return
    if loop.is_closed():
        return
    send_format = get_send_format(cmd=cmd, data=data, status=status)
    asyncio.run_coroutine_threadsafe(coro=exe(), loop=loop)


def decode(b):
    # decode Python obj to dump json data
    if isinstance(b, bytes) or isinstance(b, bytearray):
        return b.hex()
    elif isinstance(b, set) or isinstance(b, list) or isinstance(b, tuple):
        return tuple(decode(data) for data in b)
    elif isinstance(b, dict):
        return {decode(k): decode(v) for k, v in b.items()}
    else:
        return b
        # return 'Cannot decode type {}'.format(type(b))


def on_next(data):
    if isinstance(data, Block):
        send_websocket_data(cmd=CMD_NEW_BLOCK, data=data.getinfo(), is_public_data=True)
    elif isinstance(data, TX):
        send_websocket_data(cmd=CMD_NEW_TX, data=data.getinfo(), is_public_data=True)
    else:
        pass


stream.subscribe(on_next=on_next, on_error=log.error)

__all__ = [
    "CMD_ERROR",
    "CMD_NEW_BLOCK",
    "CMD_NEW_TX",
    "websocket_route",
    "send_websocket_data",
]
