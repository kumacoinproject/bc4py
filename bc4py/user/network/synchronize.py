from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.checking import check_block, check_tx, check_tx_time
from bc4py.database.builder import builder, tx_builder, user_account
from bc4py.user.network import update_mining_staking_all_info
from bc4py.user.network.directcmd import DirectCmd
from bc4py.user.network.connection import *
from bc4py.user.exit import system_exit
import logging
import time
import threading
from binascii import hexlify


f_working = False
f_changed_status = False


def fast_sync_chain():
    assert V.PC_OBJ is not None, "Need PeerClient start before."
    global f_changed_status
    start = time.time()
    block_container = dict()
    # 外部Nodeに次のBlockを逐一尋ねる
    failed_num = 0
    before_block = builder.best_block
    index_height = before_block.height + 1
    logging.debug("Start sync by {}".format(before_block))
    while failed_num < 5:
        if index_height in block_container:
            new_block = block_container[index_height]
        else:
            block_container.clear()
            r = ask_node(cmd=DirectCmd.BIG_BLOCKS, data={'height': index_height})
            if isinstance(r, str):
                logging.debug("NewBLockGetError:{}".format(r))
                before_block = builder.get_block(before_block.previous_hash)
                index_height = before_block.height + 1
                failed_num += 1
                continue
            elif isinstance(r, list):
                for block_b, block_height, block_flag, txs in r:
                    _block = Block(binary=block_b)
                    _block.height = block_height
                    _block.flag = block_flag
                    for tx_b, tx_signature in txs:
                        tx = TX(binary=tx_b)
                        tx.height = None
                        tx.signature = tx_signature
                        tx_from_database = tx_builder.get_tx(txhash=tx.hash)
                        if tx_from_database:
                            _block.txs.append(tx_from_database)
                        elif tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
                            _block.txs.append(tx)
                        else:
                            check_tx(tx, include_block=None)
                            tx_builder.put_unconfirmed(tx)
                            _block.txs.append(tx)
                        # re set height
                        tx.height = _block.height
                    block_container[block_height] = _block
                if len(block_container) == 0:
                    break
                new_block = block_container[index_height]
            else:
                failed_num += 1
                logging.debug("Not correct format BIG_BLOCKS.")
                continue
        # Base check
        if before_block.hash != new_block.previous_hash:
            logging.debug("Not correct previous hash. {}".format(new_block.height))
            before_block = builder.get_block(before_block.previous_hash)
            index_height = before_block.height + 1
            failed_num += 1
            continue
        # Block check
        check_block(new_block)
        # TX check
        for tx in new_block.txs:
            check_tx(tx, new_block)
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
                     .format(round(time.time() - start, 1), best_height_on_network, my_best_height))
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
                time.sleep(5)
            except BlockChainError as e:
                reset_good_node()
                logging.warning('Update chain failed "{}"'.format(e))
                time.sleep(5)
            except BaseException as e:
                reset_good_node()
                logging.error('Update chain failed "{}"'.format(e), exc_info=True)
                time.sleep(5)
        # out of loop
        logging.debug("Close sync loop.")

    if f_working:
        raise Exception('Already sync_chain_loop working.')
    f_working = True
    logging.info("Start sync now {} connections.".format(len(V.PC_OBJ.p2p.user)))
    threading.Thread(target=loop, name='Sync').start()
