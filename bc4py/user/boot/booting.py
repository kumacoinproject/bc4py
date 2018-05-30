from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.unconfirmed import remove_unconfirmed_tx
from bc4py.chain.genesisblock import set_genesis_block
from bc4py.database.chain.read import read_best_block_on_chain, read_blocks_by_height, \
    max_block_height, read_unconfirmed_txs, read_tx_object, fill_tx_objects
from bc4py.database.chain.write import remove_orphan_block
from bc4py.database.create import create_db, closing
from bc4py.user.network.synchronize import sync_chain_loop
from .checkpoint import update_checkpoint
from binascii import hexlify
import bjson
import logging
import os
import time
import atexit
from threading import Thread


def create_boot_file(cur, f_raise=True):
    if len(P.CHECK_POINTS) == 0:
        if f_raise:
            raise BlockChainError('Cannot find any checkpoint. Please boot at first.')
        update_checkpoint(cur=cur)
    genesis_block = read_best_block_on_chain(height=0, cur=cur)
    fill_tx_objects(block=genesis_block, cur=cur)
    with open(os.path.join(V.DB_HOME_DIR, 'boot.dat'), mode='bw') as fp:
        data = {
            'genesis block': genesis_block.b,
            'genesis txs': [tx.b for tx in genesis_block.txs],
            'checkpoints': P.CHECK_POINTS}
        bjson.dump(data, fp=fp)
    logging.debug("Recode checkpoint {}".format(len(P.CHECK_POINTS)))


def load_boot_file():
    normal_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'boot.dat')
    extra_path = os.path.join(V.DB_HOME_DIR, 'boot.dat')
    if os.path.exists(normal_path):
        with open(normal_path, mode='br') as fp:
            data = bjson.load(fp=fp)
    elif os.path.exists(extra_path):
        with open(extra_path, mode='br') as fp:
            data = bjson.load(fp=fp)
    else:
        # boot.datが無いので既存のチェーンから作成する
        with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
            cur = db.cursor()
            create_boot_file(cur, f_raise=False)
        logging.warning('Cannot find boot.dat from {} or {}. create by myself.'.format(normal_path, extra_path))
        return
    P.CHECK_POINTS.clear()
    P.CHECK_POINTS.update(data['checkpoints'])
    # 生成したオブジェクトから読み込むだけで実行はしていないはず
    genesis_block = Block(binary=data['genesis block'])
    genesis_block.height = 0
    genesis_block.flag = C.BLOCK_GENESIS
    for tx_b in data['genesis txs']:
        tx = TX(binary=tx_b)
        tx.height = 0
        genesis_block.txs.append(tx)
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as account_db:
            chain_cur = chain_db.cursor()
            # account_cur = account_db.cursor()
            try:
                original_hash = read_best_block_on_chain(height=0, cur=chain_cur).hash
                logging.debug("Already boot data exist. original={}"
                              .format(hexlify(original_hash).decode(), hexlify(genesis_block.hash).decode()))
                return
            except BlockChainError:
                pass
            set_genesis_block(genesis_block=genesis_block)
            chain_db.commit()
            account_db.commit()
    return


def auto_save_boot_file():
    def save():
        with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
            cur = db.cursor()
            create_boot_file(cur=cur, f_raise=False)
        logging.debug("Auto saved boot file.")
    # auto save
    atexit.register(save)


def start_update_chain_data(f_wait_connection=True):
    def loop():
        pc = V.PC_OBJ
        start = time.time()
        count = 20
        while f_wait_connection and len(pc.p2p.user) < 3:
            time.sleep(10)
            logging.debug("Waiting for new connection... {} {}Sec"
                          .format(len(pc.p2p.user), round(time.time() - start, 0)))
            count -= 1
        logging.debug("{} connections, start update chain data.".format(len(pc.p2p.user)))
        sync_chain_loop()
    assert V.PC_OBJ, 'Need PeerClient object'
    Thread(target=loop, name='UpdateLoop', daemon=True).start()


def vacuum_orphan_block():
    # OrphanBlockを削除する
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        removed = 0
        stable = 0
        for height in reversed(range(max_block_height(cur=cur) + 1)):
            blocks = read_blocks_by_height(height=height, cur=cur)
            if stable > C.CHECKPOINT_SPAN:
                break
            elif len(blocks) == 0:
                break
            elif len(blocks) == 1:
                stable += 1
                continue
            best_block = read_best_block_on_chain(height=height, cur=cur)
            for block in blocks:
                if block.hash != best_block.hash:
                    fill_tx_objects(block=block, cur=cur)
                    remove_orphan_block(orphan_block=block, cur=cur)
                    removed += 1
            stable = 0
        # 反映
        if 0 < removed:
            db.commit()
    # Vacuum
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        db.isolation_level = None
        db.execute('VACUUM')
    logging.debug("vacuum_orphan_block {}".format(removed))
    return removed


def initialize_unconfirmed_tx():
    remove_tx = list()
    start = time.time()
    with closing(create_db(V.DB_BLOCKCHAIN_PATH, f_on_memory=True)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH, f_on_memory=True)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            # HeightがNULLのTXを全て読み出す
            for txhash in read_unconfirmed_txs(cur=chain_cur):
                tx = read_tx_object(txhash=txhash, cur=chain_cur)
                now = int(time.time()) - V.BLOCK_GENESIS_TIME
                if tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
                    raise BlockChainError('execute vacuum_orphan_block() before initialize_unconfirmed_tx()')
                    # continue  # ProofTXは削除せず
                else:
                    if not (tx.time < now < tx.deadline + 3600):
                        remove_tx.append(tx)  # 期限切れ
                    P.UNCONFIRMED_TX.add(txhash)
            # 削除実行
            removed = list()
            for tx in remove_tx:
                removed += remove_unconfirmed_tx(tx=tx, chain_cur=chain_cur, account_cur=account_cur)
                logging.debug("Over deadline, remove unconfirmed tx {}".format(hexlify(tx.hash).decode()))
            if len(remove_tx) > 0:
                chain_db.commit()
                account_db.commit()
            logging.debug("Finish initialize unconfirmed tx removed={} unconfirmed={} {}Sec"
                          .format(len(removed), len(P.UNCONFIRMED_TX), round(time.time()-start, 3)))
            return removed
