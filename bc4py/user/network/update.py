from bc4py.config import C, V, P, Debug
from bc4py.database.builder import builder, tx_builder
from bc4py.database.tools import is_usedindex
from bc4py.database.validator import *
from bc4py.database.contract import *
from bc4py.chain.checking.utils import sticky_failed_txhash
from bc4py.user.generate import *
import logging
from collections import defaultdict
from threading import Lock, Thread
from time import time
import bjson

update_count = 0
block_lock = Lock()
unspent_lock = Lock()
unconfirmed_lock = Lock()


def update_mining_staking_all_info(u_block=True, u_unspent=True, u_unconfirmed=True):
    def _updates():
        consensus = tuple(t.consensus for t in generating_threads)
        info = ''
        if u_block and not block_lock.locked():
            info += _update_block_info()
        if u_unspent and (C.BLOCK_POS in consensus) and not unspent_lock.locked():
            info += _update_unspent_info()
        if u_unconfirmed and not unconfirmed_lock.locked():
            info += _update_unconfirmed_info()
        if info:
            logging.debug("Update finish{}".format(info))
    global update_count
    Thread(target=_updates, name='Update-{}'.format(update_count), daemon=True).start()
    update_count += 1


def _update_block_info():
    with block_lock:
        s = time()
        if builder.best_block is not None:
            update_previous_block(builder.best_block)
            return ',  height={} {}mS'.format(builder.best_block.height+1, int((time()-s)*1000))
    return ',  height=No'


def _update_unspent_info():
    with unspent_lock:
        s = time()
        all_num, next_num = update_unspents_txs()
    return ',  unspents={}/{} {}mS'.format(next_num, all_num, int((time()-s)*1000))


def _update_unconfirmed_info():
    with unconfirmed_lock:
        s = time()
        # Upgrade pre-unconfirmed to unconfirmed (check enough signature have)
        for tx in sorted(tx_builder.pre_unconfirmed.values(), key=lambda x: x.create_time):
            if tx.type == C.TX_CONCLUDE_CONTRACT:
                c_address, start_hash, c_storage = bjson.loads(tx.message)
                c = get_contract_object(c_address=c_address)
                index = start_tx2index(start_hash=start_hash)
                if c.db_index and index < c.db_index:
                    # delete
                    del tx_builder.pre_unconfirmed[tx.hash]
                    logging.debug("Delete old ConcludeTX {}".format(tx))
                    continue
            elif tx.type == C.TX_VALIDATOR_EDIT:
                c_address, new_address, flag, sig_diff = bjson.loads(tx.message)
            else:
                logging.error("Why include pre-unconfirmed? {}".format(tx))
                continue
            v = get_validator_object(c_address=c_address)
            if v.require == len(tx.signature):  # not "=<"
                # upgrade
                del tx_builder.pre_unconfirmed[tx.hash]
                tx_builder.put_unconfirmed(tx=tx)
                logging.info("Upgrade pre-unconfirmed {}".format(tx))

        # sort unconfirmed txs
        unconfirmed_txs = sorted(tx_builder.unconfirmed.values(), key=lambda x: x.gas_price, reverse=True)

        # reject tx (input tx is unconfirmed)
        limit_height = builder.best_block.height - C.MATURE_HEIGHT
        best_block, best_chain = builder.get_best_chain()
        used_pairs = set()
        for tx in unconfirmed_txs.copy():
            if tx.height is not None:
                # delete only by affect_new_chain()
                # if tx.hash in tx_builder.unconfirmed:
                #    del tx_builder.unconfirmed[tx.hash]
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
        need_resort_txs = defaultdict(list)
        for tx in unconfirmed_txs.copy():
            if tx.type == C.TX_CONCLUDE_CONTRACT:
                c_address, start_hash, c_storage = bjson.loads(tx.message)
                start_tx = tx_builder.get_tx(txhash=start_hash)
                if start_tx is None or start_tx.height is None:
                    unconfirmed_txs.remove(tx)  # start tx is confirmed
                    continue
                need_resort_txs[c_address].append(tx)
            elif tx.type == C.TX_VALIDATOR_EDIT:
                c_address, address, flag, sig_diff = bjson.loads(tx.message)
                need_resort_txs[c_address].append(tx)
            else:
                pass

        # affect resort txs (for contract)
        if len(need_resort_txs) > 0:
            append_txs = list()
            for c_address, data_list in need_resort_txs.items():
                if len(data_list) < 2:
                    continue
                for tx in sorted(data_list, key=lambda x: x.create_time):
                    unconfirmed_txs.remove(tx)
                    append_txs.append(tx)
            # resorted
            unconfirmed_txs.extend(append_txs)

        # limit per tx's in block
        if Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK:
            unconfirmed_txs = unconfirmed_txs[:Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK]

        # update
        update_unconfirmed_txs(unconfirmed_txs)
    return ',  unconfirmed={}/{}/{} {}mS'.format(len(unconfirmed_txs), len(tx_builder.unconfirmed),
                                                len(tx_builder.pre_unconfirmed), int((time()-s)*1000))
