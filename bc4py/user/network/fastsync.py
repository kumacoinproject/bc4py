from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.tx import TX
from bc4py.chain.block import Block
from bc4py.chain.signature import fill_verified_addr_many, fill_verified_addr_tx
from bc4py.chain.workhash import get_workhash_fnc, update_work_hash
from bc4py.chain.checking import new_insert_block, check_tx, check_tx_time
from bc4py.user.network.connection import *
from bc4py.user.network.update import update_info_for_generate
from bc4py.user.network.directcmd import DirectCmd
from bc4py.database.create import create_db
from bc4py.database.builder import chain_builder, tx_builder
from logging import getLogger
from time import time
from typing import List
import asyncio


loop = asyncio.get_event_loop()
log = getLogger('bc4py')
back_que = asyncio.Queue(maxsize=5)
stack_lock = asyncio.Lock()
stack_dict = dict()
stack_event = asyncio.Event()
STACK_CHUNK_SIZE = 100
PROOF_OF_WORK_FLAGS = {
    C.BLOCK_YES_POW, C.BLOCK_X11_POW, C.BLOCK_X16S_POW
}


def work_generate_future(blocks: List[Block]):
    for block in blocks:
        block.work_hash = get_workhash_fnc(block.flag)(block.b)


async def get_block_from_stack(height):
    while True:
        if height in stack_dict:
            async with stack_lock:
                block = stack_dict[height]
                del stack_dict[height]
                stack_event.clear()
            return block
        try:
            await asyncio.wait_for(stack_event.wait(), 10.0)
        except asyncio.TimeoutError:
            # timeout?
            best_height_on_network, best_hash_on_network = await get_best_conn_info()
            if height < best_height_on_network:
                await back_que.put(height)
            else:
                return None
            continue


async def back_sync_loop():
    while not P.F_STOP:
        try:
            request_height = await asyncio.wait_for(back_que.get(), 10.0)
            if request_height in stack_dict:
                continue
            block_list = await ask_random_node(cmd=DirectCmd.big_blocks, data={'height': request_height})
            block_tmp = dict()
            task_list = list()
            for block in block_list:
                block_tmp[block.height] = block
                if block.flag in PROOF_OF_WORK_FLAGS:
                    task_list.append(block)
            future: asyncio.Future = loop.run_in_executor(
                None, work_generate_future, task_list)
            await fill_verified_addr_many(block_list)
            await asyncio.wait_for(future, 10.0)
            # check
            if len(block_tmp) == 0:
                log.debug("new block is empty, finished? height={}".format(request_height))
            else:
                async with stack_lock:
                    stack_dict.update(block_tmp)
                stack_event.set()
                log.debug("success back sync from={} to={}".format(min(block_tmp), max(block_tmp)))
        except asyncio.TimeoutError:
            pass
        except BlockChainError as e:
            log.error('back loop error by "{}"'.format(e))
        except Exception:
            log.error("back_sync_loop exception", exc_info=True)
    log.info("close by F_STOP flag")


async def main_sync_loop():
    while not P.F_STOP:
        await asyncio.sleep(1.0)
        if P.F_NOW_BOOTING is False:
            continue
        if chain_builder.best_block is None:
            continue
        # start fast sync
        my_best_block: Block = chain_builder.best_block
        start_height = my_best_block.height
        start_time = time()
        # first of all
        await back_que.put(my_best_block.height + 1)
        while True:
            new_block: Block = await get_block_from_stack(my_best_block.height + 1)
            # check blockchain continuity
            if new_block is None:
                log.debug("request height is higher than network height! sync will not need?")
                stack_dict.clear()
                break
            if chain_builder.root_block is not None\
                    and chain_builder.root_block.height is not None\
                    and new_block.height <= chain_builder.root_block.height:
                log.error("cannot rollback block depth height={}".format(new_block.height))
                P.F_STOP = True
                return
            if new_block.hash in chain_builder.chain:
                log.debug("new block is already known {}".format(new_block))
                my_best_block = chain_builder.get_block(blockhash=new_block.hash)
                continue
            if my_best_block.hash != new_block.previous_hash:
                log.debug("not chained my_best_block with new_block, rollback to {}".format(my_best_block.height-1))
                my_best_block = chain_builder.get_block(blockhash=my_best_block.previous_hash)
                await back_que.put(my_best_block.height + 1)
                continue
            if len(new_block.txs) <= 0:
                log.debug("something wrong?, rollback to {}".format(my_best_block.height-1))
                my_best_block = chain_builder.get_block(blockhash=my_best_block.previous_hash)
                await back_que.put(my_best_block.height + 1)
                continue
            if new_block.work_hash is None:
                update_work_hash(new_block)
            if not new_block.pow_check():
                log.debug("unsatisfied work?, rollback to {}".format(my_best_block.height - 1))
                my_best_block = chain_builder.get_block(blockhash=my_best_block.previous_hash)
                await back_que.put(my_best_block.height + 1)
                continue
            # insert
            if not await new_insert_block(block=new_block, f_time=False, f_sign=False):
                log.debug("failed to insert new block, rollback to {}".format(my_best_block.height-1))
                my_best_block = chain_builder.get_block(blockhash=my_best_block.previous_hash)
                await back_que.put(my_best_block.height + 1)
                continue
            # request next chunk
            if len(stack_dict) < STACK_CHUNK_SIZE:
                if 0 < len(stack_dict):
                    await back_que.put(max(stack_dict) + 1)
                else:
                    await back_que.put(new_block.height + 1)
            # check reached top height
            best_height_on_network, best_hash_on_network = await get_best_conn_info()
            if new_block.height < best_height_on_network:
                my_best_block = new_block
                continue
            else:
                log.info("reached max height of network height={}".format(best_height_on_network))
                stack_dict.clear()
                break
        # get unconfirmed txs
        log.info("next get unconfirmed txs")
        unconfirmed_txhash_set = set()
        for data in await ask_all_nodes(cmd=DirectCmd.unconfirmed_tx):
            unconfirmed_txhash_set.update(data['txs'])
        unconfirmed_txs = list()
        for txhash in unconfirmed_txhash_set:
            if txhash in tx_builder.unconfirmed:
                continue
            try:
                tx: TX = await ask_random_node(cmd=DirectCmd.tx_by_hash, data={'txhash': txhash})
                tx.height = None
                await fill_verified_addr_tx(tx)
                unconfirmed_txs.append(tx)
            except BlockChainError as e:
                log.debug("1: Failed get unconfirmed {} '{}'".format(txhash.hex(), e))
        async with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = await db.cursor()
            for tx in sorted(unconfirmed_txs, key=lambda x: x.time):
                try:
                    check_tx_time(tx)
                    check_tx(tx, include_block=None)
                    await tx_builder.put_unconfirmed(cur=cur, tx=tx)
                except BlockChainError as e:
                    log.debug("2: Failed get unconfirmed '{}'".format(e))
        # fast sync finish
        log.info("fast sync finished start={} finish={} {}m".format(
            start_height, chain_builder.best_block.height, int((time() - start_time) / 60)))
        P.F_NOW_BOOTING = False
        update_info_for_generate()
    log.info("close by F_STOP flag")


async def sync_chain_loop():
    assert V.P2P_OBJ is not None, "Need PeerClient start before"
    log.info("Start sync now {} connections".format(len(V.P2P_OBJ.core.user)))
    await check_network_connection()
    asyncio.ensure_future(main_sync_loop())
    asyncio.ensure_future(back_sync_loop())


__all__ = [
    "sync_chain_loop",
]
