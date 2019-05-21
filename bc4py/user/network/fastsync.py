from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.tx import TX
from bc4py.chain.block import Block
from bc4py.chain.signature import fill_verified_addr_many
from bc4py.chain.workhash import get_workhash_fnc
from bc4py.chain.checking import new_insert_block, check_tx, check_tx_time
from bc4py.user.network.connection import *
from bc4py.user.network.update import update_info_for_generate
from bc4py.user.network.directcmd import DirectCmd
from bc4py.database.create import create_db
from bc4py.database.builder import chain_builder, tx_builder
from concurrent.futures import ThreadPoolExecutor
from threading import Thread, Event, Lock
from queue import Queue, Empty
from logging import getLogger
from time import sleep, time


log = getLogger('bc4py')
back_que = Queue(maxsize=5)
stack_lock = Lock()
stack_dict = dict()
stack_event = Event()
STACK_CHUNK_SIZE = 100
PROOF_OF_WORK_FLAGS = (
    C.BLOCK_YES_POW, C.BLOCK_X11_POW, C.BLOCK_HMQ_POW, C.BLOCK_LTC_POW, C.BLOCK_X16S_POW)


def _target(blocks):
    for block in blocks:
        block.work_hash = get_workhash_fnc(block.flag)(block.b)


def get_work_generate_future(blocks):
    with ThreadPoolExecutor(max_workers=1) as e:
        return e.submit(_target, blocks)


def get_block_from_stack(height):
    while True:
        if height in stack_dict:
            with stack_lock:
                block = stack_dict[height]
                del stack_dict[height]
                stack_event.clear()
            return block
        elif stack_event.wait(10):
            # event set!
            continue
        else:
            # timeout?
            best_height_on_network, best_hash_on_network = get_best_conn_info()
            if height < best_height_on_network:
                back_que.put(height)
            else:
                return None
            continue


def _back_loop():
    while not P.F_STOP:
        try:
            request_height = back_que.get(timeout=1)
            if request_height in stack_dict:
                continue
            block_list = seek_nodes(cmd=DirectCmd.BIG_BLOCKS, data={'height': request_height})
            block_tmp = dict()
            task_list = list()
            for block in block_list:
                block_tmp[block.height] = block
                if block.flag in PROOF_OF_WORK_FLAGS:
                    task_list.append(block)
            future = get_work_generate_future(task_list)
            fill_verified_addr_many(block_list)
            future.done()
            # check
            if len(block_tmp) == 0:
                log.debug("new block is empty, finished? height={}".format(request_height))
            else:
                with stack_lock:
                    stack_dict.update(block_tmp)
                stack_event.set()
                log.debug("success back sync from={} to={}".format(min(block_tmp), max(block_tmp)))
        except Empty:
            pass
        except BlockChainError as e:
            log.error('back loop error by "{}"'.format(e))
    log.info("close by F_STOP flag")


def _main_loop():
    while not P.F_STOP:
        sleep(1)
        if P.F_NOW_BOOTING is False:
            continue
        if chain_builder.best_block is None:
            continue
        if not back_sync_thread.is_alive():
            raise Exception('BackSync is dead!')
        # start fast sync
        my_best_block: Block = chain_builder.best_block
        start_height = my_best_block.height
        start_time = time()
        # first of all
        back_que.put(my_best_block.height + 1)
        while True:
            new_block: Block = get_block_from_stack(my_best_block.height + 1)
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
                back_que.put(my_best_block.height + 1)
                continue
            if len(new_block.txs) <= 0:
                log.debug("something wrong?, rollback to {}".format(my_best_block.height-1))
                my_best_block = chain_builder.get_block(blockhash=my_best_block.previous_hash)
                back_que.put(my_best_block.height + 1)
                continue
            # insert
            if not new_insert_block(block=new_block, f_time=False, f_sign=False):
                log.debug("failed to insert new block, rollback to {}".format(my_best_block.height-1))
                my_best_block = chain_builder.get_block(blockhash=my_best_block.previous_hash)
                back_que.put(my_best_block.height + 1)
                continue
            # request next chunk
            if len(stack_dict) < STACK_CHUNK_SIZE:
                if 0 < len(stack_dict):
                    back_que.put(max(stack_dict) + 1)
                else:
                    back_que.put(new_block.height + 1)
            # check reached top height
            best_height_on_network, best_hash_on_network = get_best_conn_info()
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
        for data in ask_all_nodes(cmd=DirectCmd.UNCONFIRMED_TX):
            unconfirmed_txhash_set.update(data['txs'])
        unconfirmed_txs = list()
        for txhash in unconfirmed_txhash_set:
            if txhash in tx_builder.unconfirmed:
                continue
            try:
                tx: TX = seek_nodes(cmd=DirectCmd.TX_BY_HASH, data={'txhash': txhash})
                tx.height = None
                unconfirmed_txs.append(tx)
            except BlockChainError as e:
                log.debug("1: Failed get unconfirmed {} '{}'".format(txhash.hex(), e))
        with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = db.cursor()
            for tx in sorted(unconfirmed_txs, key=lambda x: x.time):
                try:
                    check_tx_time(tx)
                    check_tx(tx, include_block=None)
                    tx_builder.put_unconfirmed(tx=tx, outer_cur=cur)
                except BlockChainError as e:
                    log.debug("2: Failed get unconfirmed '{}'".format(e))
        # fast sync finish
        log.info("fast sync finished start={} finish={} {}m".format(
            start_height, chain_builder.best_block.height, int((time() - start_time) / 60)))
        P.F_NOW_BOOTING = False
        update_info_for_generate()
    log.info("close by F_STOP flag")


fast_sync_thread = Thread(target=_main_loop, name='FastSync')
back_sync_thread = Thread(target=_back_loop, name='BackSync')


def sync_chain_loop():
    assert V.PC_OBJ is not None, "Need PeerClient start before"
    log.info("Start sync now {} connections".format(len(V.PC_OBJ.p2p.user)))
    check_network_connection()
    fast_sync_thread.start()
    back_sync_thread.start()
