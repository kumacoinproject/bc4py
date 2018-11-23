from bc4py.config import C, V, P, Debug
from bc4py.database.builder import builder, tx_builder
from bc4py.database.tools import is_usedindex  #,  get_validator_info
from bc4py.database.validator import get_validator_object
from bc4py.chain.checking.signature import get_signed_cks
from bc4py.chain.checking.utils import sticky_failed_txhash
from bc4py.user.generate import *
import logging
from threading import Lock, Thread
from time import time
import bjson

update_count = 0
block_lock = Lock()
unspent_lock = Lock()
unconfirmed_lock = Lock()


def update_mining_staking_all_info(u_block=True, u_unspent=True, u_unconfirmed=True):
    global update_count
    consensus = tuple(t.consensus for t in generating_threads)
    if u_block and not block_lock.locked():
        Thread(target=_update_block_info, name="B-Update{}".format(update_count)).start()
    if u_unspent and (C.BLOCK_POS in consensus) and not unspent_lock.locked():
        Thread(target=_update_unspent_info, name="U-Update{}".format(update_count)).start()
    if u_unconfirmed and not unconfirmed_lock.locked():
        Thread(target=_update_unconfirmed_info, name="C-Update{}".format(update_count)).start()
    update_count += 1


def _update_unspent_info():
    with unspent_lock:
        s = time()
        all_num, next_num = update_unspents_txs()
        logging.debug("Update unspent={}/{} {}Sec".format(next_num, all_num, round(time()-s, 3)))


def _update_block_info():
    with block_lock:
        s = time()
        if builder.best_block is not None:
            update_previous_block(builder.best_block)
            logging.debug('Update generating height={} {}Sec'
                          .format(builder.best_block.height+1, round(time()-s, 3)))


def _update_unconfirmed_info():
    with unconfirmed_lock:
        s = time()
        # sort unconfirmed txs
        unconfirmed_txs = sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time)
        unconfirmed_txs = sorted(unconfirmed_txs, key=lambda x: x.gas_price, reverse=True)

        # reject tx (input tx is unconfirmed)
        limit_height = builder.best_block.height - C.MATURE_HEIGHT
        best_block, best_chain = builder.get_best_chain()
        used_pairs = set()
        for tx in unconfirmed_txs.copy():
            if tx.height is not None:
                if tx.hash in tx_builder.unconfirmed:
                    del tx_builder.unconfirmed[tx.hash]
                unconfirmed_txs.remove(tx)
                continue
            if Debug.F_STICKY_TX_REJECTION and tx.hash in sticky_failed_txhash:
                unconfirmed_txs.remove(tx)
                continue
            # inputs check
            for txhash, txindex in tx.inputs:
                input_tx = tx_builder.get_tx(txhash)
                if input_tx is None:
                    unconfirmed_txs.remove(tx)
                    break
                elif input_tx.height is None:
                    unconfirmed_txs.remove(tx)
                    break
                elif input_tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD) and \
                        input_tx.height > limit_height:
                    unconfirmed_txs.remove(tx)
                    break
                elif is_usedindex(txhash, txindex, tx.hash, best_block, best_chain):
                    unconfirmed_txs.remove(tx)
                    break
                # check inputs used same unconfirmed_txs
                input_pair = (txhash, txindex)
                if input_pair in used_pairs:
                    unconfirmed_txs.remove(tx)
                    break
                used_pairs.add(input_pair)

        # contract tx
        for tx in unconfirmed_txs.copy():
            if tx.type == C.TX_CONCLUDE_CONTRACT:
                try:
                    c_address, start_hash, c_storage = bjson.loads(tx.message)
                except Exception:
                    unconfirmed_txs.remove(tx)  # failed decode bjson
                    continue
                start_tx = tx_builder.get_tx(txhash=start_hash)
                if start_tx is None or start_tx.height is None:
                    unconfirmed_txs.remove(tx)  # start tx is confirmed
                    continue
                v = get_validator_object(c_address=c_address, best_block=best_block, best_chain=best_chain)
                signed_cks = get_signed_cks(tx)
                accept_cks = signed_cks & set(v.validators)
                if v.require > len(accept_cks):
                    unconfirmed_txs.remove(tx)
                    continue
            elif tx.type == C.TX_VALIDATOR_EDIT:
                try:
                    c_address, address, flag, sig_diff = bjson.loads(tx.message)
                except Exception:
                    unconfirmed_txs.remove(tx)  # failed decode bjson
                    continue
                v = get_validator_object(c_address=c_address, best_block=best_block, best_chain=best_chain)
                signed_cks = get_signed_cks(tx)
                accept_cks = signed_cks & set(v.validators)
                if v.require > len(accept_cks):
                    unconfirmed_txs.remove(tx)
                    continue
            else:
                pass

        # limit per tx's in block
        if Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK:
            unconfirmed_txs = unconfirmed_txs[:Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK]

        update_unconfirmed_txs(unconfirmed_txs)
        logging.debug("Update unconfirmed={}/{} {}Sec"
                      .format(len(unconfirmed_txs), len(tx_builder.unconfirmed), round(time()-s, 3)))
