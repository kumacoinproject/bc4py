from bc4py.config import P, NewInfo
from bc4py.chain import Block, TX
from bc4py.contract.emulator.watching import *
from aiohttp import web
from threading import Thread
import asyncio
import logging
import json
from binascii import hexlify
from collections import OrderedDict

number = 0
clients = list()
loop = asyncio.get_event_loop()

CMD_NEW_BLOCK = 'Block'
CMD_NEW_TX = 'TX'
CMD_ERROR = 'Error'

# TODO: fix error: "socket.send() raised exception." => https://github.com/aio-libs/aiohttp/issues/3448


async def websocket_route(request):
    if request.rel_url.path.startswith('/public/'):
        is_public = True
    elif request.rel_url.path.startswith('/private/'):
        is_public = False
    else:
        raise web.HTTPNotFound()
    client = await websocket_protocol_check(request=request, is_public=is_public)
    async for msg in client.ws:
        try:
            if msg.type == web.WSMsgType.TEXT:
                logging.debug("Get text from {} data={}".format(client, msg.data))
                # send dummy response
                data = {'connect': len(clients), 'is_public': client.is_public, 'echo': msg.data}
                await client.send(get_send_format(cmd='debug', data=data))
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
        global number
        number += 1
        self.number = number
        self.ws = ws
        self.request = request
        self.is_public = is_public
        clients.append(self)

    def __repr__(self):
        return "<WsConnection {} {} {}>".format(
            self.number, 'Pub' if self.is_public else 'Pri', self.request.remote)

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
        channel = 'websocket'
        while not P.F_STOP:
            try:
                data = NewInfo.get(channel=channel, timeout=1)
                if isinstance(data, Block):
                    send_websocket_data(cmd=CMD_NEW_BLOCK, data=data.getinfo(), is_public_data=True)
                elif isinstance(data, TX):
                    send_websocket_data(cmd=CMD_NEW_TX, data=data.getinfo(), is_public_data=True)
                elif isinstance(data, tuple):
                    cmd, is_public, data_list = data
                    send_data = new_info2json_data(cmd=cmd, data_list=data_list)
                    if send_data:
                        send_websocket_data(cmd=cmd, data=send_data, is_public_data=is_public)
                else:
                    pass
            except NewInfo.empty:
                pass
            except Exception:
                logging.error("websocket loop error", exc_info=True)
        NewInfo.remove(channel)
        logging.info("close websocket loop.")
    Thread(target=_loop, name='WS', daemon=True).start()


def get_send_format(cmd, data, status=True):
    send_data = OrderedDict()
    send_data['cmd'] = cmd
    send_data['data'] = data
    send_data['status'] = status
    return json.dumps(send_data)


def send_websocket_data(cmd, data, status=True, is_public_data=False):
    async def exe():
        for client in clients.copy():
            if is_public_data or not client.is_public:
                await client.send(send_format)
    if P.F_NOW_BOOTING:
        return
    send_format = get_send_format(cmd=cmd, data=data, status=status)
    asyncio.run_coroutine_threadsafe(coro=exe(), loop=loop)


def new_info2json_data(cmd, data_list):
    send_data = OrderedDict()
    if cmd == C_Conclude:
        _time, tx, related_list, c_address, start_hash, c_storage = data_list
        send_data['c_address'] = c_address
        send_data['hash'] = hexlify(tx.hash).decode()
        send_data['time'] = _time
        send_data['tx'] = tx.getinfo()
        send_data['related'] = related_list
        send_data['start_hash'] = hexlify(start_hash).decode()
        send_data['c_storage'] = decode(c_storage)
    elif cmd == C_Validator:
        _time, tx, related_list, c_address, new_address, flag, sig_diff = data_list
        send_data['c_address'] = c_address
        send_data['hash'] = hexlify(tx.hash).decode()
        send_data['time'] = _time
        send_data['tx'] = tx.getinfo()
        send_data['related'] = related_list
        send_data['new_address'] = new_address
        send_data['flag'] = flag
        send_data['sig_diff'] = sig_diff
    elif cmd == C_RequestConclude:
        _time, tx, related_list, c_address, c_method, redeem_address, c_args = data_list
        send_data['c_address'] = c_address
        send_data['hash'] = hexlify(tx.hash).decode()
        send_data['time'] = _time
        send_data['tx'] = tx.getinfo()
        send_data['related'] = related_list
        send_data['c_method'] = c_method
        send_data['redeem_address'] = redeem_address
        send_data['c_args'] = decode(c_args)
    elif cmd == C_FinishConclude or cmd == C_FinishValidator:
        _time, tx = data_list
        send_data['hash'] = hexlify(tx.hash).decode()
        send_data['time'] = _time
        send_data['tx'] = tx.getinfo()
    else:
        logging.warning("Not found cmd {}".format(cmd))
    return send_data


def decode(b):
    # decode Python obj to dump json data
    if isinstance(b, bytes) or isinstance(b, bytearray):
        return hexlify(b).decode()
    elif isinstance(b, set) or isinstance(b, list) or isinstance(b, tuple):
        return tuple(decode(data) for data in b)
    elif isinstance(b, dict):
        return {decode(k): decode(v) for k, v in b.items()}
    else:
        return b
        # return 'Cannot decode type {}'.format(type(b))


__all__ = [
    "CMD_ERROR",
    "CMD_NEW_BLOCK",
    "CMD_NEW_TX",
    "start_ws_listen_loop",
    "websocket_route",
    "send_websocket_data",
]
