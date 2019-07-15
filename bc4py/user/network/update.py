from bc4py.config import C, V
from bc4py.database.builder import chain_builder, tx_builder
from bc4py.database.tools import is_unused_index_except_me
from bc4py.user.generate import *
from typing import Dict
from time import time
from logging import getLogger
from expiringdict import ExpiringDict
import asyncio


loop = asyncio.get_event_loop()
log = getLogger('bc4py')
update_count = 0
failed_txs = ExpiringDict(max_len=1000, max_age_seconds=3600)
block_lock = asyncio.Lock()
unspent_lock = asyncio.Lock()
unconfirmed_lock = asyncio.Lock()
unconfirmed_depends_hash: bytes = b''
unconfirmed_depends_cashe: Dict[bytes, tuple] = dict()


def update_info_for_generate(u_block=True, u_unspent=True, u_unconfirmed=True):

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


async def update_unconfirmed_info():
    global unconfirmed_depends_hash
    async with unconfirmed_lock:
        s = time()

        # 1: update dependency cashe
        if chain_builder.best_block.hash != unconfirmed_depends_hash:
            # require reset when best_block changed
            unconfirmed_depends_hash = chain_builder.best_block.hash
            unconfirmed_depends_cashe.clear()
        for tx in tx_builder.unconfirmed.values():
            if tx.hash in unconfirmed_depends_cashe:
                continue
            depends = list()
            for txhash, txindex in tx.inputs:
                if txhash in tx_builder.unconfirmed:
                    depends.append(tx_builder.unconfirmed[txhash])
            unconfirmed_depends_cashe[tx.hash] = tuple(depends)

        # 2: sort and get txs to include in block
        base_list = sorted(
            filter(lambda x: 0 == len(unconfirmed_depends_cashe[x.hash]), tx_builder.unconfirmed.values()),
            key=lambda x: x.gas_price, reverse=True)
        optionals = sorted(
            filter(lambda x: 0 < len(unconfirmed_depends_cashe[x.hash]), tx_builder.unconfirmed.values()),
            key=lambda x: x.gas_price, reverse=True)
        # add optionals if block space is enough
        base_list_size = sum(tx.size for tx in base_list)
        optional_size = sum(tx.size for tx in optionals)
        over_size_list = None
        unconfirmed_txs = None
        if C.SIZE_BLOCK_LIMIT >= 80 + base_list_size:
            if C.SIZE_BLOCK_LIMIT >= 80 + base_list_size + optional_size:
                # base+optionals is smaller than limit
                unconfirmed_txs = base_list
                unconfirmed_txs.extend(optionals)
            else:
                # base is smaller but base+optionals is larger than limit
                over_size_list = base_list
                over_size_list.extend(optionals)
        else:
            # base is larger than limit
            over_size_list = base_list

        if unconfirmed_txs is None:
            sum_size = 80  # with block header
            for index, tx in enumerate(over_size_list):
                sum_size += tx.size
                if C.SIZE_BLOCK_LIMIT < sum_size:
                    unconfirmed_txs = over_size_list[:index]  # do not include the tx
                    break
            else:
                raise Exception(f"over sized but not break")
            unconfirmed_txs.sort(key=lambda x: x.create_time)
        elif over_size_list is None:
            unconfirmed_txs.sort(key=lambda x: x.create_time)
        else:
            raise Exception('both over_size_list and unconfirmed_txs is not None')

        # 3: remove unconfirmed outputs using txs
        limit_height = chain_builder.best_block.height - C.MATURE_HEIGHT
        best_block, best_chain = chain_builder.get_best_chain()
        for tx in unconfirmed_txs.copy():
            if tx.height is not None:
                unconfirmed_txs.remove(tx)  # already confirmed
                continue
            if 0 < len(unconfirmed_depends_cashe[tx.hash]):
                skip = False
                for depend_tx in unconfirmed_depends_cashe[tx.hash]:
                    if depend_tx not in unconfirmed_txs:
                        # not found depend in unconfirmed
                        continue
                    if unconfirmed_txs.index(tx) < unconfirmed_txs.index(depend_tx):
                        # the tx' depends use newer input!
                        unconfirmed_txs.remove(tx)
                        skip = True
                        break
                if skip:
                    continue

            # tx's inputs check
            for txhash, txindex in tx.inputs:
                input_tx = tx_builder.get_account_tx(txhash)
                if input_tx is None:
                    # not found input tx
                    unconfirmed_txs.remove(tx)
                    break
                elif input_tx.height is None:
                    # use unconfirmed tx's outputs
                    unconfirmed_txs.remove(tx)
                    break
                if input_tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
                    if input_tx.height > limit_height:
                        # too young generated outputs
                        unconfirmed_txs.remove(tx)
                        break
                if not is_unused_index_except_me(
                        input_hash=txhash,
                        input_index=txindex,
                        except_hash=tx.hash,
                        best_block=best_block,
                        best_chain=best_chain):
                    # ERROR: already used outputs
                    unconfirmed_txs.remove(tx)
                    break
            await asyncio.sleep(0.0)

        # 4. update unconfirmed txs
        update_unconfirmed_txs(unconfirmed_txs)

    return ',  unconfirmed={}/{} {}mS'.format(
        len(unconfirmed_txs), len(tx_builder.unconfirmed), int((time() - s) * 1000))


__all__ = [
    "update_info_for_generate",
]
