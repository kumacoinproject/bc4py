from bc4py.config import V, P, Debug
from bc4py.database.create import create_db, closing
from bc4py.user.boot.checkpoint import update_checkpoint
from bc4py.database.chain.read import max_block_height, read_best_block, fill_tx_objects
from bc4py.chain.unconfirmed import update_unconfirmed_tx, get_unconfirmed_tx
from bc4py.user.utxo import get_unspent
import logging
from threading import Lock
import time


global_update_status_lock = Lock()


"""def update_mining_staking_all_info_old():
    with global_update_status_lock:
        now = int(time.time())
        with closing(create_db(V.DB_BLOCKCHAIN_PATH, f_on_memory=True)) as chain_db:
            with closing(create_db(V.DB_ACCOUNT_PATH, f_on_memory=True)) as account_db:
                chain_cur = chain_db.cursor()
                account_cur = account_db.cursor()

                mining = V.MINING_OBJ
                staking = V.STAKING_OBJ

                top_height = max_block_height(cur=chain_cur)
                base_block = read_best_block(height=top_height, cur=chain_cur)

                update_checkpoint(cur=chain_cur)
                fill_tx_objects(block=base_block, cur=chain_cur)
                removed_tx = update_unconfirmed_tx(chain_cur=chain_cur, account_cur=account_cur)
                if len(removed_tx) > 0:
                    chain_db.commit()
                    account_db.commit()
                    logging.debug("Removed unconfirmed {}".format(len(removed_tx)))
                unconfirmed_txs = get_unconfirmed_tx(cur=chain_cur)
                if Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK:
                    unconfirmed_txs = unconfirmed_txs[:Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK]
        if mining.f_mining:
            mining.update_block(base_block=base_block)
            mining.update_unconfirmed(unconfirmed=unconfirmed_txs)
        if staking.f_staking:
            staking.update_block(base_block=base_block)
            staking.update_unconfirmed(unconfirmed=unconfirmed_txs)
            unspent, orphan = get_unspent(chain_cur, account_cur)
            staking.update_unspent(unspent=unspent)
        logging.info("Next Height={} staking={} unconfirmed={}/{} removed={}"
                     .format(base_block.height+1, staking.thread_pool, len(unconfirmed_txs),
                             len(P.UNCONFIRMED_TX), len(removed_tx)))"""


def update_mining_staking_all_info(u_block=True, u_unspent=True, u_unconfirmed=True):
    locked_time = time.time()
    with global_update_status_lock:
        unlocked_time = time.time()
        with closing(create_db(V.DB_BLOCKCHAIN_PATH, f_on_memory=True)) as chain_db:
            with closing(create_db(V.DB_ACCOUNT_PATH, f_on_memory=True)) as account_db:
                chain_cur = chain_db.cursor()
                account_cur = account_db.cursor()
                removed_tx = list()

                if u_block:
                    _update_block_info(chain_cur=chain_cur)
                    update_checkpoint(cur=chain_cur)
                    removed_tx = update_unconfirmed_tx(chain_cur=chain_cur, account_cur=account_cur)
                if u_unspent:
                    _update_unspent_info(chain_cur=chain_cur, account_cur=account_cur)
                if u_unconfirmed:
                    _update_unconfirmed_info(chain_cur=chain_cur)
                if 0 < len(removed_tx):
                    chain_db.commit()
                    account_db.commit()
                    logging.debug("Removed unconfirmed {}".format(len(removed_tx)))
    logging.debug("Update finished {}Sec (Wait{}Sec)"
                  .format(round(time.time()-unlocked_time, 3), round(locked_time-unlocked_time, 3)))


def _update_unspent_info(chain_cur, account_cur):
    unspent, orphan = get_unspent(chain_cur, account_cur)
    if V.STAKING_OBJ.f_staking:
        V.STAKING_OBJ.update_unspent(unspent=unspent)
    logging.debug("Update unspent={} orphan={}".format(len(unspent), len(orphan)))


def _update_block_info(chain_cur):
    top_height = max_block_height(cur=chain_cur)
    base_block = read_best_block(height=top_height, cur=chain_cur)
    fill_tx_objects(block=base_block, cur=chain_cur)
    if V.MINING_OBJ.f_mining:
        V.MINING_OBJ.update_block(base_block=base_block)
    if V.STAKING_OBJ.f_staking:
        V.STAKING_OBJ.update_block(base_block=base_block)
    logging.debug('Update next height={}'.format(top_height+1))


def _update_unconfirmed_info(chain_cur):
    unconfirmed_txs = get_unconfirmed_tx(cur=chain_cur)
    if Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK:
        unconfirmed_txs = unconfirmed_txs[:Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK]
    if V.MINING_OBJ.f_mining:
        V.MINING_OBJ.update_unconfirmed(unconfirmed=unconfirmed_txs)
    if V.STAKING_OBJ.f_staking:
        V.STAKING_OBJ.update_unconfirmed(unconfirmed=unconfirmed_txs)
    logging.debug("Update unconfirmed={}/{}"
                  .format(len(unconfirmed_txs), len(P.UNCONFIRMED_TX)))
