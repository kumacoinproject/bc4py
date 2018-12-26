from bc4py.config import C, V, P, Debug, BlockChainError
from bc4py.database.builder import builder, tx_builder
from bc4py.database.tools import is_usedindex
from bc4py.database.validator import *
from bc4py.database.contract import *
from bc4py.chain.checking.signature import get_signed_cks
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
        # check upgrade pre-unconfirmed
        if len(tx_builder.pre_unconfirmed) > 0:
            check_upgradable_pre_unconfirmed()

        # sort unconfirmed txs
        unconfirmed_txs = sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time)
        pruning_over_size_unconfirmed(unconfirmed_txs)

        # reject tx (inputs is unconfirmed)
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

        # check validator tx
        sort_validator_txs = defaultdict(list)
        default_validator = DefaultValidator(best_block=best_block, best_chain=best_chain)
        for tx in unconfirmed_txs.copy():
            if tx.type == C.TX_VALIDATOR_EDIT:
                c_address, address, flag, sig_diff = bjson.loads(tx.message)
                v_before = default_validator[c_address]
                if not signature_acceptable(v=v_before, tx=tx):
                    unconfirmed_txs.remove(tx)
                    continue
                sort_validator_txs[c_address].append(tx)
                v_before.update(db_index=None, flag=flag, address=address, sig_diff=sig_diff)
                unconfirmed_txs.remove(tx)
        # check contract tx
        sort_contract_txs = defaultdict(list)
        for tx in unconfirmed_txs.copy():
            if tx.type == C.TX_CONCLUDE_CONTRACT:
                c_address, start_hash, c_storage = bjson.loads(tx.message)
                start_tx = tx_builder.get_tx(txhash=start_hash)
                if start_tx is None or start_tx.height is None:
                    unconfirmed_txs.remove(tx)  # start tx is unconfirmed
                    continue
                v = default_validator[c_address]
                if not signature_acceptable(v=v, tx=tx):
                    unconfirmed_txs.remove(tx)
                    continue
                index = start_tx2index(start_tx=start_tx)
                sort_contract_txs[c_address].append((tx, index))
                unconfirmed_txs.remove(tx)

        # resort contract/validator txs
        # [proof]-[normal]-..-[normal]-[validator]-..-[validator]-[contract]-..-[contract]
        append_txs = list()
        if len(sort_validator_txs) > 0:
            for c_address, tx_list in sort_validator_txs.items():
                for tx in tx_list:
                    append_txs.append(tx)
        if len(sort_contract_txs) > 0:
            for c_address, sort_data in sort_contract_txs.items():
                c_first = get_contract_object(  # best index on memory
                    c_address=c_address, best_block=best_block, best_chain=best_chain)
                index_before = c_first.db_index
                for tx, index in sorted(sort_data, key=lambda x: x[1]):
                    if index_before:
                        c_before = get_contract_object(c_address=c_address, stop_txhash=tx.hash)
                        if index_before != c_before.db_index:
                            break  # skip
                    append_txs.append(tx)
                    index_before = index
        if len(append_txs) > 0:
            unconfirmed_txs.extend(append_txs)
            logging.debug("Append {} ConcludeTX/Validator TX".format(len(append_txs)))

        # limit per tx's in block
        if Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK:
            unconfirmed_txs = unconfirmed_txs[:Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK]

        # update
        update_unconfirmed_txs(unconfirmed_txs)
    return ',  unconfirmed={}/{}/{} {}mS'.format(len(unconfirmed_txs), len(tx_builder.unconfirmed),
                                                 len(tx_builder.pre_unconfirmed), int((time()-s)*1000))


def check_upgradable_pre_unconfirmed():
    # upgrade pre-unconfirmed => unconfirmed (check enough signature have)
    # caution: provisional check, need to check order and signature after!
    for tx in sorted(tx_builder.pre_unconfirmed.values(), key=lambda x: x.create_time):
        if tx.hash in tx_builder.unconfirmed:
            del tx_builder.pre_unconfirmed[tx.hash]
            logging.debug("Remove from pre-unconfirmed, already unconfirmed. {}".format(tx))
            continue
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
        # check upgradable
        v = get_validator_object(c_address=c_address)
        if v.require <= len(tx.signature):
            del tx_builder.pre_unconfirmed[tx.hash]
            tx_builder.put_unconfirmed(tx=tx)
            logging.info("Upgrade pre-unconfirmed {}".format(tx))


def signature_acceptable(v: Validator, tx):
    signed_cks = get_signed_cks(tx)
    accept_cks = set(v.validators) & signed_cks
    return v.require <= len(accept_cks)


def pruning_over_size_unconfirmed(unconfirmed_txs: list):
    original_num = len(unconfirmed_txs)
    full_size = sum(tx.size + len(tx.signature) * 96 for tx in unconfirmed_txs)
    full_size += 80  # block header size
    unconfirmed_txs.sort(key=lambda x: x.gas_price, reverse=True)
    while full_size > C.SIZE_BLOCK_LIMIT:
        tx = unconfirmed_txs.pop()
        full_size -= tx.size + len(tx.signature) * 96
    if len(unconfirmed_txs) != original_num:
        logging.debug("Purged unconfirmed txs {}/{}".format(len(unconfirmed_txs), original_num))


class DefaultValidator(dict):
    def __init__(self, best_block, best_chain):
        super().__init__()
        self.best_block = best_block
        self.best_chain = best_chain

    def __missing__(self, key):
        ret = self[key] = get_validator_object(
            c_address=key, best_block=self.best_block, best_chain=self.best_chain)
        return ret


class DefaultContract(dict):
    def __init__(self, best_block, best_chain):
        super().__init__()
        self.best_block = best_block
        self.best_chain = best_chain

    def __missing__(self, key):
        ret = self[key] = get_contract_object(
            c_address=key, best_block=self.best_block, best_chain=self.best_chain)
        return ret
