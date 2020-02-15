from bc4py.config import C
from bc4py.database.builder import chain_builder, tx_builder
from bc4py.database.tools import is_unused_index_except_me
from typing import Dict
from time import time
import asyncio


unconfirmed_lock = asyncio.Lock()
optimized_unconfirmed_list = list()  # 80 + tx_sizes < SIZE_BLOCK_LIMIT
unconfirmed_depends_hash: bytes = b''
unconfirmed_depends_cache: Dict[bytes, tuple] = dict()


async def update_unconfirmed_info():
    global unconfirmed_depends_hash
    async with unconfirmed_lock:
        s = time()

        # 1: update dependency cache
        if chain_builder.best_block.hash != unconfirmed_depends_hash:
            # require reset when best_block changed
            unconfirmed_depends_hash = chain_builder.best_block.hash
            unconfirmed_depends_cache.clear()
        for tx in tx_builder.unconfirmed.values():
            if tx.hash in unconfirmed_depends_cache:
                continue
            depends = list()
            for txhash, txindex in tx.inputs:
                if txhash in tx_builder.unconfirmed:
                    depends.append(tx_builder.unconfirmed[txhash])
            unconfirmed_depends_cache[tx.hash] = tuple(depends)

        # 2: sort and get txs to include in block
        base_list = sorted(
            filter(lambda x: 0 == len(unconfirmed_depends_cache[x.hash]), tx_builder.unconfirmed.values()),
            key=lambda x: x.gas_price, reverse=True)
        optionals = sorted(
            filter(lambda x: 0 < len(unconfirmed_depends_cache[x.hash]), tx_builder.unconfirmed.values()),
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
                unconfirmed_txs.remove(tx)
                # log.debug("remove unconfirmed: already confirmed")
                continue
            if 0 < len(unconfirmed_depends_cache[tx.hash]):
                skip = False
                for depend_tx in unconfirmed_depends_cache[tx.hash]:
                    if depend_tx not in unconfirmed_txs:
                        # not found depend in unconfirmed
                        continue
                    if unconfirmed_txs.index(tx) < unconfirmed_txs.index(depend_tx):
                        unconfirmed_txs.remove(tx)
                        # log.debug("remove unconfirmed: the tx' depends use newer input!")
                        skip = True
                        break
                if skip:
                    continue

            # tx's inputs check
            for txhash, txindex in tx.inputs:
                input_tx = tx_builder.get_memorized_tx(txhash)
                if input_tx is not None:
                    if input_tx.height is None:
                        unconfirmed_txs.remove(tx)
                        # log.debug("remove unconfirmed: use unconfirmed tx's outputs")
                        break
                    if input_tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
                        if input_tx.height > limit_height:
                            unconfirmed_txs.remove(tx)
                            # log.debug("remove unconfirmed: too young generated outputs")
                            break

                if not is_unused_index_except_me(
                        input_hash=txhash,
                        input_index=txindex,
                        except_hash=tx.hash,
                        best_block=best_block,
                        best_chain=best_chain):
                    unconfirmed_txs.remove(tx)
                    # log.debug("remove unconfirmed: already used outputs")
                    break

            # switch event loop
            await asyncio.sleep(0.0)

        # 4. update unconfirmed txs
        optimized_unconfirmed_list.clear()
        optimized_unconfirmed_list.extend(unconfirmed_txs)

    return ',  unconfirmed={}/{} {}mS'.format(
        len(unconfirmed_txs), len(tx_builder.unconfirmed), int((time() - s) * 1000))


__all__ = [
    "unconfirmed_lock",
    "optimized_unconfirmed_list",
    "update_unconfirmed_info",
]
