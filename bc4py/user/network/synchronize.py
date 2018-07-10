from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.checking import check_block, check_tx, check_tx_time
from bc4py.database.builder import builder, tx_builder, user_account
from bc4py.user.network import update_mining_staking_all_info
from bc4py.user.network.directcmd import DirectCmd
import logging
import random
import collections
import time
import threading


good_node = list()
bad_node = list()
best_hash_on_network = None
best_height_on_network = None
f_changed_status = False


def set_good_node():
    _node = list()
    pc = V.PC_OBJ
    blockhash = collections.Counter()
    blockheight = collections.Counter()
    for _user in pc.p2p.user:
        try:
            dummy, r = pc.send_direct_cmd(cmd=DirectCmd.BEST_INFO, data=None, user=_user)
            if isinstance(r, str):
                continue
        except TimeoutError:
            continue
        blockhash[r['hash']] += 1
        blockheight[r['height']] += 1
        _node.append((_user, r['hash'], r['height'], r['booting']))
    global best_hash_on_network, best_height_on_network
    best_hash_on_network, num0 = blockhash.most_common()[0]
    best_height_on_network, num1 = blockheight.most_common()[0]
    good_node.clear()
    bad_node.clear()
    for _user, _hash, _height, _booting in _node:
        if num0 == num1 == 1:
            if not _booting:
                good_node.append(_user)
            else:
                bad_node.append(_user)
        elif num0 == 1:
            if _height == best_height_on_network:
                good_node.append(_user)
            else:
                bad_node.append(_user)
        else:
            good_node.append(_user)


def reset_good_node():
    good_node.clear()
    global best_hash_on_network, best_height_on_network
    best_hash_on_network = None
    best_height_on_network = None


def ask_node(cmd, data=None, f_continue_asking=False):
    count = 10
    pc = V.PC_OBJ
    while 0 < count:
        try:
            user = random.choice(pc.p2p.user)
            if user in bad_node:
                count -= 1
                continue
            elif user not in good_node:
                set_good_node()
                if len(good_node) == 0:
                    raise BlockChainError('No good node found.')
                else:
                    logging.debug("Get good node {}".format(len(good_node)))
                    continue
            dummy, r = pc.send_direct_cmd(cmd=cmd, data=data, user=user)
            if f_continue_asking and isinstance(r, str):
                if count > 0:
                    count -= 1
                    continue
                else:
                    raise BlockChainError('Node return error "{}"'.format(r))
        except TimeoutError:
            continue
        except IndexError:
            raise BlockChainError('No node found.')
        return r
    raise BlockChainError('Too many retry ask_node.')


def sync_chain_data():
    assert V.PC_OBJ is not None, "Need PeerClient start before."
    global f_changed_status
    start = time.time()
    # 内部の最新のBlock
    try:
        previous_hash = builder.best_block.hash
        previous_height = builder.best_block.height
    except BlockChainError as e:
        logging.fatal('Failed by inner error, broken chain. "{}"'.format(e))
        exit(1)
        return False
    # 外部Nodeに次のBlockを逐一尋ねる
    count = 5
    while count > 0:
        r = ask_node(cmd=DirectCmd.BLOCK_BY_HEIGHT, data={'height': previous_height + 1})
        if isinstance(r, str):
            logging.debug("NewBlockInfoException1:{}".format(r))
            previous_height -= 1
            previous_hash = builder.get_block_hash(previous_height)
            count -= 1
            continue
        r = ask_node(cmd=DirectCmd.BLOCK_BY_HASH, data=r, f_continue_asking=True)
        if isinstance(r, str):
            logging.debug("NewBlockInfoException2:{}".format(r))
            count -= 1
            continue
        new_block = Block(binary=r['block'])
        new_block.height = previous_height + 1
        new_block.flag = r['flag']
        if r['orphan']:
            previous_height -= 1
            previous_hash = builder.get_block_hash(previous_height)
            count -= 1
            continue
        elif new_block.previous_hash != previous_hash:
            previous_height -= 1
            previous_hash = builder.get_block_hash(previous_height)
            count -= 1
            continue
        elif builder.get_block(new_block.hash):
            previous_height += 1
            previous_hash = new_block.hash
            count -= 1
            continue
        # TXを補充
        for tx_dict in r['txs']:
            tx = TX(binary=tx_dict['tx'])
            tx.height = None
            tx.signature = tx_dict['sign']
            tx_from_database = tx_builder.get_tx(txhash=tx.hash)
            if tx_from_database:
                new_block.txs.append(tx_from_database)
            elif tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
                new_block.txs.append(tx)
            else:
                check_tx(tx, include_block=None)
                tx_builder.put_unconfirmed(tx)
                new_block.txs.append(tx)
            # re set height
            tx.height = new_block.height
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
        count = 5
        previous_height += 1
        previous_hash = new_block.hash
        # ロギング
        if previous_height % 100 == 0:
            logging.debug("Update block {} now...".format(previous_height+1))
    # Unconfirmed txを取得
    r = ask_node(cmd=DirectCmd.UNCONFIRMED_TX, f_continue_asking=True)
    if isinstance(r, dict):
        for txhash in r['txs']:
            r = ask_node(cmd=DirectCmd.TX_BY_HASH, data={'txhash': txhash}, f_continue_asking=True)
            tx = TX(binary=r['tx'])
            try:
                tx.signature = r['sign']
                check_tx_time(tx)
                check_tx(tx, include_block=None)
                tx_builder.put_unconfirmed(tx)
            except BlockChainError:
                logging.debug("Failed get unconfirmed {}".format(tx))
    elif isinstance(r, list):
        for tx_dict in r:
            tx = TX(binary=tx_dict['tx'])
            try:
                tx.signature = tx_dict['sign']
                check_tx(tx, include_block=None)
                tx_builder.put_unconfirmed(tx)
            except BlockChainError:
                logging.debug("Failed get unconfirmed {}".format(tx))
    # 最終判断
    reset_good_node()
    set_good_node()
    my_best_height = builder.best_block.height
    if best_height_on_network <= my_best_height:
        logging.info("Finish update chain data by network. {}Sec [{}<={}]"
                     .format(round(time.time()-start, 1), best_height_on_network, my_best_height))
        return True
    else:
        logging.debug("Continue update chain, {}<={}".format(best_height_on_network, my_best_height))
        return False


f_working = False


def sync_chain_loop():
    global f_working

    def loop():
        global f_changed_status
        failed = 5
        while True:
            try:
                if P.F_NOW_BOOTING:
                    if sync_chain_data():
                        P.F_NOW_BOOTING = False
                        if builder.best_block:
                            update_mining_staking_all_info(f_force=True)
                    elif failed < 0:
                        exit_msg = 'You may in fork chain. please delete "db" from "blockchain-py" folder,' \
                                   ' and resync blockchain. Close resync now.'
                        break
                    elif f_changed_status is False:
                        failed -= 1
                    elif f_changed_status is True:
                        f_changed_status = False
                    reset_good_node()
                time.sleep(10)
            except BlockChainError as e:
                reset_good_node()
                logging.warning('Update chain failed "{}"'.format(e), exc_info=True)
                time.sleep(10)
            except BaseException as e:
                reset_good_node()
                logging.error('Update chain failed "{}"'.format(e), exc_info=True)
                time.sleep(10)
        # out of loop
        logging.critical(exit_msg)

    if f_working:
        raise Exception('Already sync_chain_loop working.')
    f_working = True
    P.F_NOW_BOOTING = True
    c = 0
    while len(V.PC_OBJ.p2p.user) < 3:
        if c % 10 == 0:
            logging.debug("Waiting for new connections.. {}".format(len(V.PC_OBJ.p2p.user)))
        time.sleep(15)
        c += 1
    logging.info("Start sync now {} connections.".format(len(V.PC_OBJ.p2p.user)))
    threading.Thread(target=loop, name='Sync').start()
