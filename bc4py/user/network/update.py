from bc4py.config import C
from bc4py.database.builder import chain_builder
from bc4py.user.unconfirmed import unconfirmed_lock, update_unconfirmed_info
from bc4py.user.generate import *
from logging import getLogger
from time import time
import asyncio


loop = asyncio.get_event_loop()
log = getLogger('bc4py')
update_count = 0
block_lock = asyncio.Lock()
unspent_lock = asyncio.Lock()


def update_info_for_generate(u_block=True, u_unspent=True, u_unconfirmed=True):
    """update generating status, used only on network fnc"""

    async def updates(num):
        try:
            consensus = tuple(t.consensus for t in generating_threads)
            info = ''
            if u_block and not block_lock.locked():
                info += await update_block_info()
            if u_unspent and (C.BLOCK_COIN_POS in consensus) and not unspent_lock.locked():
                info += await update_unspent_info()
            if u_unconfirmed and not unconfirmed_lock.locked():
                info += await update_unconfirmed_info()
            if info:
                log.debug("{} update finish{}".format(num, info))
        except Exception:
            log.debug("update_info_for_generate exception", exc_info=True)

    global update_count
    asyncio.ensure_future(updates(update_count))
    update_count += 1


async def update_block_info():
    async with block_lock:
        while chain_builder.best_block is None:
            await asyncio.sleep(0.2)
        update_previous_block(chain_builder.best_block)
        return ',  height={}'.format(chain_builder.best_block.height + 1)


async def update_unspent_info():
    async with unspent_lock:
        s = time()
        all_num, next_num = await update_unspents_txs()
    return ',  unspents={}/{} {}mS'.format(next_num, all_num, int((time() - s) * 1000))


__all__ = [
    "update_info_for_generate",
]
