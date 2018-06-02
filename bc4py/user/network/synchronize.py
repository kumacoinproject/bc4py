from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.manage import insert_to_chain, global_chain_lock, check_tx, add_tx_as_new
from bc4py.database.create import create_db, closing
from bc4py.database.chain.read import max_block_height, read_best_block_on_chain, read_tx_object, read_tx_output
from bc4py.database.chain.flag import is_include_txhash, is_include_blockhash
from bc4py.user.utxo import add_utxo_user
from bc4py.user.network import update_mining_staking_all_info
from .directcmd import DirectCmd
import logging
import random
import collections
import time
from binascii import hexlify


good_node = list()
best_hash_on_network = None
best_height_on_network = None


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
    if num0 == num1 == 1:
        good_node.extend([_user for _user, _hash, _height, _booting in _node if not _booting])
    elif num0 == 1:
        good_node.extend([_user for _user, _hash, _height, _booting in _node if _height == best_height_on_network])
    else:
        good_node.extend([_user for _user, _hash, _height, _booting in _node if _hash == best_hash_on_network])
    if len(good_node) <= 1:
        good_node.extend([_user for _user, _hash, _height, _booting in _node])


def reset_good_node():
    good_node.clear()
    global best_hash_on_network
    best_hash_on_network = None


def ask_node(cmd, data=None, f_continue_asking=False):
    count = 10
    pc = V.PC_OBJ
    while True:
        try:
            user = random.choice(pc.p2p.user)
            if user not in good_node:
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


def fill_newblock(new_block, txs, next_height, next_hash, chain_cur):
    for txhash in txs:
        if is_include_txhash(txhash=txhash, cur=chain_cur):
            tx = read_tx_object(txhash=txhash, cur=chain_cur)
            tx.height = next_height
        else:
            r2 = ask_node(cmd=DirectCmd.TX_BY_HASH, data={'txhash': txhash}, f_continue_asking=True)
            if isinstance(r2, str):
                next_hash = new_block.previous_hash
                next_height -= 1
                return True, next_height, next_hash
            else:
                tx = TX(binary=r2['tx'])
                tx.height = next_height
                tx.signature = r2['sign']

        # POS-TXの追加
        if tx.type == C.TX_POS_REWARD:
            txhash, txindex = tx.inputs[0]
            if is_include_txhash(txhash=txhash, cur=chain_cur):
                address, coin_id, amount = read_tx_output(txhash=txhash, txindex=txindex, cur=chain_cur)
                tx.pos_amount = amount
            else:
                # originalのTXがみつからない？
                next_hash = new_block.previous_hash
                next_height -= 1
                return True, next_height, next_hash
        # Blockに追加
        new_block.txs.append(tx)
    return False, next_height, next_hash


def sync_chain_data():
    assert V.PC_OBJ is not None, "Need PeerClient start before."
    start = time.time()
    with closing(create_db(V.DB_BLOCKCHAIN_PATH, f_wal_mode=True)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH, f_wal_mode=True)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()

            # 内部の最新のBlock
            try:
                check_height = max_block_height(cur=chain_cur)
                my_best_block = read_best_block_on_chain(height=check_height, cur=chain_cur)
                next_hash = my_best_block.hash
                next_height = my_best_block.height
            except BlockChainError as e:
                logging.fatal('Failed by inner error, broken chain. "{}"'.format(e))
                exit(1)
                return False

            # 外部Nodeに次のBlockを逐一尋ねる
            while True:
                r = ask_node(cmd=DirectCmd.BLOCK_BY_HASH, data={'blockhash': next_hash})
                if isinstance(r, str):
                    logging.debug("NewBlockInfoException:{}".format(r))
                    my_best_block = read_best_block_on_chain(height=next_height-1, cur=chain_cur)
                    next_hash = my_best_block.hash
                    next_height = my_best_block.height
                    continue
                new_block = Block(binary=r['block'])
                new_block.height = next_height
                new_block.flag = r['flag']
                if r['orphan']:
                    next_hash = new_block.previous_hash
                    next_height -= 1
                    continue

                # TX objectを補充
                f_get_previous_block, next_height, next_hash = fill_newblock(
                    new_block=new_block, txs=r['txs'],
                    next_height=next_height, next_hash=next_hash, chain_cur=chain_cur)

                # Chainに加える
                if f_get_previous_block:
                    continue
                elif is_include_blockhash(blockhash=new_block.hash, cur=chain_cur):
                    # 既に追加済み
                    next_hash = r['next_hash']
                    next_height += 1
                elif insert_to_chain(new_block=new_block, chain_cur=chain_cur,
                                     account_cur=account_cur, f_check_time=False):
                    chain_db.commit()
                    account_db.commit()
                    # 次のBlock準備
                    next_hash = r['next_hash']
                    next_height += 1
                else:
                    chain_db.rollback()
                    account_db.rollback()
                    next_hash = new_block.previous_hash
                    next_height -= 1
                    continue

                # Break条件チェック
                if best_hash_on_network == new_block.hash:
                    logging.debug("Now on best block {}".format(hexlify(best_hash_on_network).decode()))
                    break
                elif next_hash is None:
                    logging.debug("Next hash is None, now on best chain.")
                    break

                # ロギング
                if next_height < 10 or next_height % 100 == 0:
                    logging.debug("Update block {} now...".format(next_height))
                    time.sleep(0.1)

            # Unconfirmed txを取得
            r = ask_node(cmd=DirectCmd.UNCONFIRMED_TX, f_continue_asking=True)
            for txhash in r['txs']:
                if is_include_txhash(txhash=txhash, cur=chain_cur):
                    P.UNCONFIRMED_TX.add(txhash)
                    continue
                else:
                    r2 = ask_node(cmd=DirectCmd.TX_BY_HASH, data={'txhash': txhash}, f_continue_asking=True)
                    new_tx = TX(binary=r2['tx'])
                    new_tx.height = None
                    new_tx.signature = r2['sign']
                try:
                    check_tx(tx=new_tx, include_block=None, cur=chain_cur)
                    add_tx_as_new(new_tx=new_tx, chain_cur=chain_cur, account_cur=account_cur)
                    add_utxo_user(tx=new_tx, chain_cur=chain_cur, account_cur=account_cur)
                    chain_db.commit()
                    account_db.commit()
                except BlockChainError as e:
                    logging.debug("Reject tx {}".format(new_tx.getinfo()))
                    chain_db.rollback()
                    account_db.rollback()
            # 最終判断
            reset_good_node()
            set_good_node()
            my_best_height = max_block_height(cur=chain_cur)
            if best_height_on_network <= my_best_height:
                logging.info("Finish update chain data by network. {}Sec [{}<={}]"
                             .format(round(time.time()-start, 1), best_height_on_network, my_best_height))
                return True
            else:
                return False


def sync_chain_loop():
    while True:
        try:
            if P.F_NOW_BOOTING:
                with global_chain_lock:
                    P.F_SYNC_DIRECT_IMPORT = True
                    if sync_chain_data():
                        P.F_NOW_BOOTING = False
                        update_mining_staking_all_info()
                    P.F_SYNC_DIRECT_IMPORT = False
                    reset_good_node()
            time.sleep(5)
        except BlockChainError as e:
            P.F_SYNC_DIRECT_IMPORT = False
            reset_good_node()
            logging.warning('Update chain failed "{}"'.format(e), exc_info=True)
            time.sleep(10)
