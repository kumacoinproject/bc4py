from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.checking import check_block, check_tx, check_tx_time
from bc4py.chain.checking.signature import batch_sign_cashe
from bc4py.chain.workhash import get_workhash_fnc
from bc4py.database.builder import builder, tx_builder, user_account
from bc4py.database.create import closing, create_db
from bc4py.user.network import update_mining_staking_all_info
from bc4py.user.network.directcmd import DirectCmd
from bc4py.user.network.connection import *
from bc4py.user.exit import system_exit
from pooled_multiprocessing import mp_map_async, Waiter
import logging
from time import time, sleep
from threading import Thread, Lock
from binascii import hexlify


f_working = False
f_changed_status = False
block_stack = dict()
backend_processing_lock = Lock()
write_protect_lock = Lock()


def _generate_workhash(height, block_flag, block_b, **kwargs):
    # TODO: warning, check memory leak
    return height, get_workhash_fnc(block_flag)(block_b)


def _callback_workhash(data_list):
    if isinstance(data_list[0], str):
        logging.error("error on callback_workhash(), {}".format(data_list[0]))
        return
    block_stack_copy = block_stack.copy()
    for height, workhash in data_list:
        if height in block_stack_copy:
            block_stack_copy[height].work_hash = workhash
    logging.debug("callback_workhash() workhash={}".format(len(data_list)))


def batch_workhash(blocks):
    data_list = list()
    s = time()
    for block in blocks:
        if block.flag in (C.BLOCK_YES_POW, C.BLOCK_HMQ_POW, C.BLOCK_X11_POW, C.BLOCK_LTC_POW, C.BLOCK_X16R_POW):
            data_list.append((block.height, block.flag, block.b))
    if len(data_list) > 0:
        waiter, result = mp_map_async(_generate_workhash, data_list, callback=_callback_workhash)
        logging.debug("Success batch workhash {} by {}Sec".format(len(data_list), round(time()-s, 3)))
        return waiter
    else:
        waiter = Waiter(0)
        waiter.set()
        return waiter


def put_to_block_stack(r, before_waiter):
    block_tmp = dict()
    batch_txs = list()
    for block_b, block_height, block_flag, txs in r:
        block = Block(binary=block_b)
        block.height = block_height
        block.flag = block_flag
        for tx_b, tx_signature in txs:
            tx = TX(binary=tx_b)
            tx.height = None
            tx.signature = tx_signature
            tx_from_database = tx_builder.get_tx(txhash=tx.hash)
            if tx_from_database:
                block.txs.append(tx_from_database)
            else:
                block.txs.append(tx)
        block_tmp[block_height] = block
        batch_txs.extend(block.txs)
    # check
    if len(block_tmp) == 0:
        return None
    batch_sign_cashe(batch_txs)
    before_waiter.wait()
    with write_protect_lock:
        block_stack.update(block_tmp)
    return batch_workhash(tuple(block_tmp.values()))


def fill_block_stack(before_waiter):
    if len(block_stack) == 0:
        return None
    height = max(block_stack) + 1
    logging.debug("Stack blocks on back form {}".format(height))
    r = ask_node(cmd=DirectCmd.BIG_BLOCKS, data={'height': height}, f_continue_asking=True)
    if isinstance(r, str):
        logging.debug("NewBLockGetError:{}".format(r))
    elif isinstance(r, list):
        return put_to_block_stack(r, before_waiter)
    else:
        logging.debug("Not correct format BIG_BLOCKS.")
    return None


def background_sync_chain():
    waiter = Waiter(0)
    waiter.set()
    sleep_count = 500
    while True:
        if sleep_count < 0:
            logging.info("Close background_sync_chain() by timeout.")
            return
        if len(block_stack) == 0:
            sleep(0.1)
            sleep_count -= 1
        elif 400 < len(block_stack):
            sleep(0.1)
        else:
            sleep_count = 500
            with backend_processing_lock:
                waiter = fill_block_stack(waiter)
            if waiter is None:
                logging.info("Close background_sync_chain() by finish.")
                return


def fast_sync_chain():
    assert V.PC_OBJ is not None, "Need PeerClient start before."
    global f_changed_status
    back_thread = Thread(target=background_sync_chain, name='BackSync', daemon=True)
    back_thread.start()
    start = time()

    # 外部Nodeに次のBlockを逐一尋ねる
    failed_num = 0
    before_block = builder.best_block
    index_height = before_block.height + 1
    logging.debug("Start sync by {}".format(before_block))
    while failed_num < 5:
        if index_height in block_stack:
            new_block = block_stack[index_height]
            with write_protect_lock:
                del block_stack[index_height]
        elif backend_processing_lock.locked():
            sleep(0.1)
            continue
        else:
            with backend_processing_lock:
                logging.debug("Stack blocks on front form {}".format(index_height))
                r = ask_node(cmd=DirectCmd.BIG_BLOCKS, data={'height': index_height})
                if isinstance(r, str):
                    logging.debug("NewBLockGetError:{}".format(r))
                    before_block = builder.get_block(before_block.previous_hash)
                    index_height = before_block.height + 1
                    failed_num += 1
                    continue
                elif isinstance(r, list):
                    waiter = Waiter(0)
                    waiter.set()
                    waiter = put_to_block_stack(r, waiter)
                    if waiter is None or len(block_stack) == 0:
                        break
                    else:
                        waiter.wait()
                        continue
                else:
                    failed_num += 1
                    logging.debug("Not correct format BIG_BLOCKS.")
                    continue
        # Base check
        base_check_failed_msg = None
        if before_block.hash != new_block.previous_hash:
            base_check_failed_msg = "Not correct previous hash {}".format(new_block)
        # proof of work check
        if not new_block.pow_check():
            base_check_failed_msg = "Not correct work hash {}".format(new_block)
        # rollback
        if base_check_failed_msg is not None:
            before_block = builder.get_block(before_block.previous_hash)
            index_height = before_block.height + 1
            failed_num += 1
            for height in tuple(block_stack.keys()):
                if height >= index_height:
                    del block_stack[height]
            logging.debug(base_check_failed_msg)
            continue
        # TX check
        if len(new_block.txs) > 1:
            with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
                cur = db.cursor()
                for tx in new_block.txs:
                    if tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
                        continue
                    check_tx(tx=tx, include_block=None)
                    tx_builder.put_unconfirmed(tx=tx, outer_cur=cur)
                db.commit()
        # Block check
        check_block(new_block)
        for tx in new_block.txs:
            tx.height = new_block.height
            check_tx(tx=tx, include_block=new_block)
        # Chainに挿入
        builder.new_block(new_block)
        for tx in new_block.txs:
            user_account.affect_new_tx(tx)
        builder.batch_apply()
        f_changed_status = True
        # 次のBlock
        failed_num = 0
        before_block = new_block
        index_height = before_block.height + 1
        # ロギング
        if index_height % 100 == 0:
            logging.debug("Update block {} now...".format(index_height + 1))
    # Unconfirmed txを取得
    logging.info("Finish get block, next get unconfirmed.")
    r = None
    while not isinstance(r, dict):
        r = ask_node(cmd=DirectCmd.UNCONFIRMED_TX, f_continue_asking=True)
    for txhash in r['txs']:
        if txhash in tx_builder.unconfirmed:
            continue
        try:
            r = ask_node(cmd=DirectCmd.TX_BY_HASH, data={'txhash': txhash}, f_continue_asking=True)
            tx = TX(binary=r['tx'])
            tx.signature = r['sign']
            check_tx_time(tx)
            check_tx(tx, include_block=None)
            tx_builder.put_unconfirmed(tx)
        except BlockChainError:
            logging.debug("Failed get unconfirmed {}".format(hexlify(txhash).decode()))
    # 最終判断
    reset_good_node()
    set_good_node()
    my_best_height = builder.best_block.height
    best_height_on_network, best_hash_on_network = get_best_conn_info()
    if best_height_on_network <= my_best_height:
        logging.info("Finish update chain data by network. {}Sec [{}<={}]"
                     .format(round(time() - start, 1), best_height_on_network, my_best_height))
        return True
    else:
        logging.debug("Continue update chain, {}<={}".format(best_height_on_network, my_best_height))
        return False


def sync_chain_loop():
    global f_working

    def loop():
        global f_changed_status, f_working
        failed = 5
        while f_working:
            check_connection()
            try:
                if P.F_NOW_BOOTING:
                    if fast_sync_chain():
                        P.F_NOW_BOOTING = False
                        if builder.best_block:
                            update_mining_staking_all_info()
                        builder.remove_failmark()
                    elif failed < 0:
                        exit_msg = 'Failed sync.'
                        builder.make_failemark(exit_msg)
                        logging.critical(exit_msg)
                        system_exit()
                        f_working = False
                    elif f_changed_status is False:
                        failed -= 1
                    elif f_changed_status is True:
                        f_changed_status = False
                    reset_good_node()
                sleep(5)
            except BlockChainError as e:
                reset_good_node()
                logging.warning('Update chain failed "{}"'.format(e))
                sleep(5)
            except BaseException as e:
                reset_good_node()
                logging.error('Update chain failed "{}"'.format(e), exc_info=True)
                sleep(5)
        # out of loop
        logging.debug("Close sync loop.")

    if f_working:
        raise Exception('Already sync_chain_loop working.')
    f_working = True
    logging.info("Start sync now {} connections.".format(len(V.PC_OBJ.p2p.user)))
    Thread(target=loop, name='Sync').start()


def close_sync():
    global f_working
    f_working = False
