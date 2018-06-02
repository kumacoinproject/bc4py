from bc4py.config import V, P, Debug
from aiohttp import web
from weakref import WeakValueDictionary
from binascii import hexlify
import asyncio
import logging
import json
import time
import queue


class Cmd:
    # send command
    NewBlock = 'NewBlock'
    NewTX = 'NewTX'
    SystemChange = 'SystemChange'
    ChannelData = 'ChannelData'
    Others = 'Others'
    RaisedError = 'RaisedError'
    # receive command
    AddChannel = 'AddChannel'
    RemoveChannel = 'RemoveChannel'
    ListChannel = 'ListChannel'


class Ch:
    NewBlock = 'NewBlock'
    NewTX = 'NewTX'
    SystemChange = 'SystemChange'


async def ws_streaming(request):
    try:
        client = await websocket_protocol_check(request)

        async for msg in client.ws:
            try:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    command = data['cmd']
                    if command == Cmd.AddChannel:
                        await client.add_channel(data['channel'])
                    elif command == Cmd.RemoveChannel:
                        await client.remove_channel(data['channel'])
                    elif command == Cmd.ListChannel:
                        await client.send(Cmd.ListChannel, client.channels)
                elif msg.type == web.WSMsgType.BINARY:
                    print(2, msg.data)
                    await client.ws.send_bytes(msg.data)
                elif msg.type == web.WSMsgType.CLOSED:
                    print(3, "closed")
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(4, "error")
                    break
            except BaseException as e:
                import traceback
                await client.send_error(e=traceback.format_exc() if Debug.F_WS_FULL_ERROR_MSG else e)
            logging.debug("close websocket.")

        return client.ws
    except BaseException as e:
        return web.Response(text=str(e), status=400)


async def websocket_protocol_check(request):
    ws = web.WebSocketResponse()
    available = ws.can_prepare(request)
    if not available:
        raise TypeError('Cannot prepare websocket.')
    await ws.prepare(request)
    logging.debug("protocol upgrade to websocket.")
    client = Client(ws, request)
    request.app['sockets'][client.name] = client
    return client


async def event_wait_blockchain(app):
    que = queue.LifoQueue()
    P.NEW_CHAIN_INFO_QUE = que
    logging.debug("start blockchain event loop.")
    while True:
        await asyncio.sleep(0.1)
        try:
            data = que.get_nowait()
        except queue.Empty:
            continue
        if 'work_hash' in data:
            cmd = Cmd.NewBlock
        elif 'signature' in data:
            cmd = Cmd.NewTX
        else:
            cmd = Cmd.Others
        for client in app['sockets'].values():
            await client.send(cmd=cmd, data=data)


async def change_find_system_info(app):
    def status():
        return len(V.PC_OBJ.p2p.user), P.F_NOW_BOOTING, P.UNCONFIRMED_TX.copy()
    old_connections = status()
    while True:
        await asyncio.sleep(1)
        if old_connections == status():
            continue
        old_connections = status()
        data = {
            'connections': len(V.PC_OBJ.p2p.user),
            'booting': P.F_NOW_BOOTING,
            'unconfirmed': [hexlify(txhash).decode() for txhash in P.UNCONFIRMED_TX]}
        for client in app['sockets'].values():
            await client.send(cmd=Cmd.SystemChange, data=data)


def init_ws_status(app):
    async def on_shutdown(app):
        for client in app['sockets'].values():
            await client.ws.close()
        app['sockets'].clear()
    app.on_shutdown.append(on_shutdown)
    app['sockets'] = WeakValueDictionary()
    loop = asyncio.get_event_loop()
    asyncio.run_coroutine_threadsafe(event_wait_blockchain(app), loop)
    asyncio.run_coroutine_threadsafe(change_find_system_info(app), loop)


class Client:
    def __init__(self, ws, request):
        self.name = id(ws)
        self.ws = ws
        self.request = request
        self.channels = list()

    def add_channel(self, channel):
        if channel not in self.channels:
            self.channels.append(channel)

    def remove_channel(self, channel):
        if channel in self.channels:
            self.channels.remove(channel)

    async def send(self, cmd, data):
        j = json.dumps({"cmd": cmd, "data": data, "time": time.time()})
        await self.ws.send_str(j)

    async def send_error(self, e):
        j = json.dumps({"cmd": Cmd.RaisedError, "data": str(e), "time": time.time()})
        await self.ws.send_str(j)

    async def send_others(self, cmd, data):
        j = json.dumps({"cmd": cmd, "data": data, "time": time.time()})
        for client in self.request['sockets'].values():
            if client.ws is not self.ws:
                await self.ws.send_str(j)

    async def sendall(self, cmd, data):
        j = json.dumps({"cmd": cmd, "data": data, "time": time.time()})
        for client in self.request['sockets'].values():
            await client.ws.send_str(j)

    async def send_channel(self, data, channel):
        j = json.dumps({"cmd": Cmd.ChannelData, 'channel': channel, "data": data, "time": time.time()})
        for client in self.request['sockets'].values():
            if channel in client.channels:
                await client.ws.send_str(j)


__all__ = [
    "ws_streaming",
    "init_ws_status",
]
