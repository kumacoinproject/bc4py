from bc4py.config import P, NewInfo
from bc4py.chain import Block, TX
from aiohttp import web
from threading import Thread
import asyncio
import logging
import json
import time


clients = list()
loop = asyncio.get_event_loop()

CMD_NEW_BLOCK = 'Block'
CMD_NEW_TX = 'TX'
CMD_ERROR = 'Error'


async def websocket_public(request):
    client = await websocket_protocol_check(request=request, is_public=True)
    async for msg in client.ws:
        try:
            if msg.type == web.WSMsgType.TEXT:
                logging.debug("Get text from {} data={}".format(client, msg.data))
            elif msg.type == web.WSMsgType.BINARY:
                logging.debug("Get bin from {} data={}".format(client, msg.data))
            elif msg.type == web.WSMsgType.CLOSED:
                await client.close()
            elif msg.type == web.WSMsgType.ERROR:
                logging.error("Get error from {} data={}".format(client, msg.data))
        except Exception as e:
            import traceback
            await client.send(raw_data=get_send_format(
                cmd=CMD_ERROR, data=str(traceback.format_exc()), status=False))
        logging.debug("close {}".format(client))
    return client.ws


async def websocket_private(request):
    client = await websocket_protocol_check(request=request, is_public=False)
    async for msg in client.ws:
        try:
            if msg.type == web.WSMsgType.TEXT:
                logging.debug("Get text from {} data={}".format(client, msg.data))
            elif msg.type == web.WSMsgType.BINARY:
                logging.debug("Get bin from {} data={}".format(client, msg.data))
            elif msg.type == web.WSMsgType.CLOSED:
                logging.debug("Get close signal from {} data={}".format(client, msg.data))
                break
            elif msg.type == web.WSMsgType.ERROR:
                logging.error("Get error from {} data={}".format(client, msg.data))
        except Exception as e:
            import traceback
            await client.send(raw_data=get_send_format(
                cmd=CMD_ERROR, data=str(traceback.format_exc()), status=False))
    logging.debug("close {}".format(client))
    await client.close()
    return client.ws


async def websocket_protocol_check(request, is_public):
    ws = web.WebSocketResponse()
    available = ws.can_prepare(request)
    if not available:
        raise TypeError('Cannot prepare websocket.')
    await ws.prepare(request)
    logging.debug("protocol upgrade to websocket. {}".format(request.remote))
    return WsConnection(ws=ws, request=request, is_public=is_public)


class WsConnection:
    def __init__(self, ws, request, is_public):
        self.ws = ws
        self.request = request
        self.is_public = is_public
        clients.append(self)

    def __repr__(self):
        return "<WsConnection {} {}>".format(
            'Pub' if self.is_public else 'Pri', self.request.remote)

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


def start_ws_listen_loop():
    def _loop():
        logging.info("start websocket loop.")
        while not P.F_STOP:
            try:
                data = NewInfo.get(channel='websocket', timeout=1)
                if isinstance(data, Block):
                    send_websocket_data(cmd=CMD_NEW_BLOCK, data=data.getinfo(), is_public_data=True)
                elif isinstance(data, TX):
                    send_websocket_data(cmd=CMD_NEW_TX, data=data.getinfo(), is_public_data=True)
                elif isinstance(data, tuple):
                    cmd, is_public, send_data = data
                    send_websocket_data(cmd=cmd, data=send_data, is_public_data=is_public)
            except NewInfo.empty:
                pass
        logging.info("close websocket loop.")
    Thread(target=_loop, name='WS', daemon=True).start()


def get_send_format(cmd, data, status=True):
    return json.dumps(
        {"cmd": cmd, "data": data, "time": time.time(), 'status': status})


def send_websocket_data(cmd, data, status=True, is_public_data=False):
    async def exe():
        for client in clients.copy():
            if is_public_data or not client.is_public:
                await client.send(send_format)
    if P.F_NOW_BOOTING:
        return
    send_format = get_send_format(cmd=cmd, data=data, status=status)
    asyncio.run_coroutine_threadsafe(coro=exe(), loop=loop)


__all__ = [
    "CMD_ERROR",
    "CMD_NEW_BLOCK",
    "CMD_NEW_TX",
    "start_ws_listen_loop",
    "websocket_public",
    "websocket_private",
    "send_websocket_data",
]
