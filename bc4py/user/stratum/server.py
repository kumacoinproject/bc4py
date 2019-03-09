from bc4py.config import C, P
from bc4py.user.generate import *
from bc4py.user.stratum.command import *
from bc4py.database.builder import builder
from expiringdict import ExpiringDict
from collections import deque
import asyncio
import json
from time import time
import warnings
from logging import getLogger

log = getLogger('bc4py')

# https://asyncio.readthedocs.io/en/latest/tcp_echo.html
# https://en.bitcoin.it/wiki/Stratum_mining_protocol
# https://slushpool.com/help/manual/stratum-protocol
# https://techmedia-think.hatenablog.com/entry/2016/04/17/114519
# https://github.com/ctubio/php-proxy-stratum/wiki/Stratum-Mining-Protocol

loop = asyncio.get_event_loop()
stratum = list()
job_queue = ExpiringDict(max_len=100, max_age_seconds=300)

ERROR_CODES = [
    (20, "Other / Unknown", None),
    (21, "- Job not found", None),  # = stale
    (22, "- Duplicate share", None),
    (23, "- Low difficulty share", None),
    (24, "- Unauthorized worker", None),
    (25, "- Not subscribed", None)
]

F_DEEP_DEBUG = True


class Stratum:

    def __init__(self, port, consensus, first_difficulty=128, f_local=True):
        warnings.warn("not work", ResourceWarning)
        self.consensus = consensus
        self.first_difficulty = first_difficulty
        host = '127.0.0.1' if f_local else '0.0.0.0'
        coro = asyncio.start_server(self._handle, host, port)
        self.server = loop.run_until_complete(coro)
        log.info("Stratum work on {}".format(self.server.sockets[0].getsockname()))
        self.users = dict()
        stratum.append(self)

    def __repr__(self):
        return "<Stratum {} {} users={}>".format(C.consensus2name[self.consensus], self.first_difficulty,
                                                 len(self.users))

    def close(self):
        self.server.close()
        loop.run_until_complete(self.server.wait_closed())

    async def broadcast(self, method, params):
        for reader, writer in self.users.keys():
            try:
                writer.write(json.dumps({'id': None, 'method': method, 'params': params}).encode() + b'\n')
                await writer.drain()
            except Exception as e:
                log.error(e)

    async def _handle(self, reader, writer):
        recv_msg = b''
        user = dict(user=None, password=None, deque=deque(maxlen=10), diff=self.first_difficulty)
        self.users[(reader, writer)] = user
        data = dict()
        while True:
            try:
                recv_msg += await reader.read(1024)
                if len(recv_msg) == 0:
                    break
                if b'\n' not in recv_msg:
                    continue
                message, recv_msg = recv_msg.split(b'\n', 1)
                message = message.decode()
                data = json.loads(message)
                await self._process(writer, data, user)
            except ConnectionResetError as e:
                break
            except StratumError as e:
                writer.write(
                    json.dumps({
                        "id": data.get('id'),
                        "result": None,
                        "error": ERROR_CODES[0]
                    }).encode() + b'\n')
                await writer.drain()
                log.debug("StratumError: {}".format(e))
            except Exception:
                log.error("Stratum", exc_info=True)
        log.info("ConnectionClosed.")
        del self.users[(reader, writer)]
        writer.close()

    async def _process(self, writer, data, user):
        if F_DEEP_DEBUG: log.debug("Input: {}".format(data))
        args = data['params']
        method_name = '_'.join(data['method'].split('.'))
        async_method = globals().get(method_name, None)
        if not isinstance(args, list):
            raise StratumError('args is list.')
        if async_method is None:
            raise StratumError('Not found method "{}" by params is "{}"'.format(method_name, args))
        kwords = dict(self=self, job_queue=job_queue, user=user, writer=writer)
        result = await async_method(*args, **kwords)
        writer.write(json.dumps({'id': data['id'], 'result': result, 'error': None}).encode() + b'\n')
        await writer.drain()
        if F_DEEP_DEBUG: log.debug("Output: {}".format(result))


async def reset_difficulty():
    target_span = 5.0
    count = 0
    for p in stratum:
        for (writer, reader), user in p.users:
            if len(user.deque) < 2:
                new_diff = user.diff
            else:
                span = (max(user.deque) - min(user.deque)) / (len(user.deque) - 1)
                bias = min(2.0, max(0.5, target_span / span))
                new_diff = user.diff * bias
            writer.write(
                json.dumps({
                    "id": None,
                    "method": "mining.set_difficulty",
                    "params": [new_diff]
                }).encode() + b'\n')
            await writer.drain()
            count += 1
    log.debug("Update diff {} users.".format(count))


async def backend_process():
    # Check new block loop.
    best_block_hash = builder.best_block.hash
    job_id = 0
    last_notify_update = time()
    while True:
        while P.F_NOW_BOOTING:
            await asyncio.sleep(0.2)
        if time() - last_notify_update > 60.0:
            last_notify_update = time()
            clean_jobs = False
        elif best_block_hash is not builder.best_block.hash:
            clean_jobs = True
        else:
            await asyncio.sleep(0.2)
            continue
        # detect new block!
        try:
            best_block_hash = builder.best_block.hash
            for s in stratum:
                job_id += 1
                mining_block = create_mining_block(consensus=s.consensus)
                job_queue[job_id] = mining_block
                params = await mining_notify(job_id, clean_jobs, mining_block)
                await s.broadcast('mining.notify', params)
                if F_DEEP_DEBUG: log.debug("Notify {}".format(params))
        except Exception as e:
            import traceback
            traceback.print_exc()
            log.error(e)
        log.debug("Update new job {} height={}".format(job_id, builder.best_block.height))
        # notify new diff if new job
        if clean_jobs:
            await reset_difficulty()


def start_stratum(f_blocking=True):
    asyncio.run_coroutine_threadsafe(backend_process(), loop)
    # Serve requests until Ctrl+C is pressed
    if f_blocking:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        loop.close()
        log.info("Stratum server closed now.")
    else:
        log.info("Create Stratum server.")


def close_stratum():
    for s in stratum:
        s.close()


class StratumError(Exception):
    pass


__all__ = [
    "Stratum",
    "start_stratum",
    "close_stratum",
]
