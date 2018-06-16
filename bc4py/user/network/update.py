from bc4py.config import C, V, P, Debug
from bc4py.database.builder import builder, tx_builder
from bc4py.database.tools import get_contract_storage
import logging
from threading import Lock, Thread
import time
import bjson


global_update_status_lock = Lock()
update_count = 0


def update_mining_staking_all_info(u_block=True, u_unspent=True, u_unconfirmed=True):
    global update_count
    Thread(target=_update,
           args=(u_block, u_unspent, u_unconfirmed), name='Update{}'.format(update_count)).start()
    update_count += 1


def _update(u_block, u_unspent, u_unconfirmed):
    t = time.time()
    with global_update_status_lock:
        if u_block:
            _update_block_info()
        if u_unspent:
            _update_unspent_info()
        if u_unconfirmed:
            _update_unconfirmed_info()
    logging.debug("Update finished {}Sec".format(round(time.time() - t, 3)))


def _update_unspent_info():
    if V.STAKING_OBJ.f_staking:
        next_num = V.STAKING_OBJ.update_unspent()
        logging.debug("Update unspent={}".format(next_num))


def _update_block_info():
    if V.MINING_OBJ.f_mining:
        V.MINING_OBJ.update_block(builder.best_block)
    if V.STAKING_OBJ.f_staking:
        V.STAKING_OBJ.update_block(builder.best_block)
    if V.MINING_OBJ.f_mining or V.STAKING_OBJ.f_staking:
        logging.debug('Update generating height={}'.format(builder.best_block.height+1))


def _update_unconfirmed_info():
    # sort unconfirmed txs
    unconfirmed_txs = sorted(tx_builder.unconfirmed.values(), key=lambda x: x.gas_price, reverse=True)
    if Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK:
        unconfirmed_txs = unconfirmed_txs[:Debug.F_LIMIT_INCLUDE_TX_IN_BLOCK]
    unconfirmed_txs = sorted(unconfirmed_txs, key=lambda x: x.time)

    # ContractTXのみ取り出す
    contract_txs = dict()
    for tx in unconfirmed_txs.copy():
        if tx.type == C.TX_START_CONTRACT:
            unconfirmed_txs.remove(tx)
            if tx not in contract_txs:
                contract_txs[tx] = list()
        elif tx.type == C.TX_FINISH_CONTRACT:
            unconfirmed_txs.remove(tx)
            dummy0, start_hash, dummy1 = bjson.loads(tx.message)
            if start_hash not in tx_builder.unconfirmed:
                continue
            start_tx = tx_builder.unconfirmed[start_hash]
            if start_tx in contract_txs:
                contract_txs[start_tx].append(tx)
            if start_tx in unconfirmed_txs:
                contract_txs[start_tx] = [tx]

    # StartTX=>FinishTXを一対一関係で繋げる
    validator_cs = get_contract_storage(V.CONTRACT_VALIDATOR_ADDRESS)
    validators = 0
    for k, v in validator_cs.items():
        if k.startswith(b'\x00') and v == b'\x01':
            validators += 1
    need_validators = validators * 2 // 3 + 1
    for start_tx, finish_txs in contract_txs.items():
        if len(finish_txs) == 0:
            continue
        for tx in finish_txs:
            if len(tx.signature) < need_validators:
                continue
            # OK!
            unconfirmed_txs.extend((start_tx, tx))
            break

    if V.MINING_OBJ.f_mining:
        V.MINING_OBJ.update_unconfirmed(unconfirmed_txs)
    if V.STAKING_OBJ.f_staking:
        V.STAKING_OBJ.update_unconfirmed(unconfirmed_txs)
    if V.MINING_OBJ.f_mining or V.STAKING_OBJ.f_staking:
        logging.debug("Update unconfirmed={}/{}"
                      .format(len(unconfirmed_txs), len(tx_builder.unconfirmed)))
