from bc4py.config import C, V, P, executor, executor_lock, BlockChainError
from bc4py.chain.tx import TX
from bc4py.chain.block import Block
from bc4py.chain.signature import batch_sign_cashe
from bc4py.chain.workhash import get_workhash_fnc
from bc4py.chain.checking import new_insert_block, check_tx, check_tx_time
from bc4py.user.network.connection import *
from bc4py.user.network.update import update_info_for_generate
from bc4py.user.network.directcmd import DirectCmd
from bc4py.database.create import create_db
from bc4py.database.builder import builder, tx_builder
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


def _work(task_list):
    result = list()
    for height, flag, binary in task_list:
        try:
            hashed = get_workhash_fnc(flag)(binary)
            result.append((height, hashed))
        except Exception as e:
            result.append((height, str(e)))
    return result


def throw_hash_generate_task(task_list, block_list):
    with executor_lock:
        future = executor.submit(_work, task_list)
    block_dict = {block.height: block for block in block_list}
    data_list = future.result()
    if len(data_list) == 0:
        return
    for height, hashed in data_list:
        if isinstance(hashed, str):
            log.error('error on generate hash: "{}"'.format(hashed))
        elif height in block_dict:
            block_dict[height].work_hash = hashed
        else:
            log.warning("not found height on stack_dict? height={}".format(height))


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
                batch_sign_cashe(txs=block.txs, b_block=block.b)
                block_tmp[block.height] = block
                if block.flag not in (C.BLOCK_GENESIS, C.BLOCK_CAP_POS, C.BLOCK_COIN_POS, C.BLOCK_FLK_POS):
                    task_list.append((block.height, block.flag, block.b))
            throw_hash_generate_task(task_list, block_list)
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
        if builder.best_block is None:
            continue
        if not back_sync_thread.is_alive():
            raise Exception('BackSync is dead!')
        # start fast sync
        my_best_block: Block = builder.best_block
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
            if builder.root_block is not None\
                    and builder.root_block.height is not None\
                    and new_block.height <= builder.root_block.height:
                log.error("cannot rollback block depth height={}".format(new_block.height))
                P.F_STOP = True
                return
            if new_block.hash in builder.chain:
                log.debug("new block is already known {}".format(new_block))
                my_best_block = builder.get_block(blockhash=new_block.hash)
                continue
            if my_best_block.hash != new_block.previous_hash:
                log.debug("not chained my_best_block with new_block, rollback to {}".format(my_best_block.height-1))
                my_best_block = builder.get_block(blockhash=my_best_block.previous_hash)
                back_que.put(my_best_block.height + 1)
                continue
            if len(new_block.txs) <= 0:
                log.debug("something wrong?, rollback to {}".format(my_best_block.height-1))
                my_best_block = builder.get_block(blockhash=my_best_block.previous_hash)
                back_que.put(my_best_block.height + 1)
                continue
            # insert
            if not new_insert_block(block=new_block, f_time=False, f_sign=False):
                log.debug("failed to insert new block, rollback to {}".format(my_best_block.height-1))
                my_best_block = builder.get_block(blockhash=my_best_block.previous_hash)
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
        log.info("fast sync finished start={} finish={} {}mSec".format(
            start_height, builder.best_block.height, int((time()-start_time)/60)))
        P.F_NOW_BOOTING = False
        update_info_for_generate()
    log.info("close by F_STOP flag")


fast_sync_thread = Thread(target=_main_loop, name='FastSync')
back_sync_thread = Thread(target=_back_loop, name='BackSync')


def sync_chain_loop():
    assert V.PC_OBJ is not None, "Need PeerClient start before"
    log.info("Start sync now {} connections.".format(len(V.PC_OBJ.p2p.user)))
    check_network_connection()
    fast_sync_thread.start()
    back_sync_thread.start()
