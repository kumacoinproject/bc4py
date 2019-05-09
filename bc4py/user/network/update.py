from bc4py.config import C, V
from bc4py.database.builder import builder, tx_builder
from bc4py.database.tools import is_usedindex
from bc4py.database.validator import *
from bc4py.database.contract import *
from bc4py.chain.checking.checktx import check_unconfirmed_order
from bc4py.chain.signature import get_signed_cks
from bc4py.user.generate import *
from threading import Lock, Thread
from time import time, sleep
from logging import getLogger
from expiringdict import ExpiringDict

log = getLogger('bc4py')
update_count = 0
failed_txs = ExpiringDict(max_len=1000, max_age_seconds=3600)
block_lock = Lock()
unspent_lock = Lock()
unconfirmed_lock = Lock()


def update_info_for_generate(u_block=True, u_unspent=True, u_unconfirmed=True):

    def _updates():
        consensus = tuple(t.consensus for t in generating_threads)
        info = ''
        if u_block and not block_lock.locked():
            info += _update_block_info()
        if u_unspent and (C.BLOCK_COIN_POS in consensus) and not unspent_lock.locked():
            info += _update_unspent_info()
        if u_unconfirmed and not unconfirmed_lock.locked():
            info += _update_unconfirmed_info()
        if info:
            log.debug("Update finish{}".format(info))

    global update_count
    Thread(target=_updates, name='Update-{}'.format(update_count), daemon=True).start()
    update_count += 1


def _update_block_info():
    with block_lock:
        while builder.best_block is None:
            sleep(0.2)
        update_previous_block(builder.best_block)
        return ',  height={}'.format(builder.best_block.height + 1)


def _update_unspent_info():
    with unspent_lock:
        s = time()
        all_num, next_num = update_unspents_txs()
    return ',  unspents={}/{} {}mS'.format(next_num, all_num, int((time() - s) * 1000))


def _update_unconfirmed_info():
    with unconfirmed_lock:
        s = time()
        prune_limit = s - 10

        # 1: check upgradable pre-unconfirmed
        for tx in sorted(tx_builder.pre_unconfirmed.values(), key=lambda x: x.create_time):
            try:
                if tx.create_time > prune_limit:
                    continue  # too young tx
                if not (tx.time - C.ACCEPT_MARGIN_TIME < s - V.BLOCK_GENESIS_TIME <
                        tx.deadline + C.ACCEPT_MARGIN_TIME):
                    del tx_builder.pre_unconfirmed[tx.hash]
                    log.debug("Remove from pre-unconfirmed, over deadline. {}".format(tx))
                    continue
                if tx.hash in tx_builder.unconfirmed:
                    del tx_builder.pre_unconfirmed[tx.hash]
                    log.debug("Remove from pre-unconfirmed, already unconfirmed. {}".format(tx))
                    continue
                # check by tx type
                if tx.type == C.TX_CONCLUDE_CONTRACT:
                    c_address, start_hash, c_storage = tx.encoded_message()
                    c = get_contract_object(c_address=c_address)
                    if c.version > -1:
                        index = start_tx2index(start_hash=start_hash)
                        if index <= c.db_index:
                            del tx_builder.pre_unconfirmed[tx.hash]
                            log.debug("remove, too old {}<{} {}".format(index, c.db_index, tx))
                            continue
                        else:
                            # c.db_index < index
                            # accept correct ordered
                            pass
                        v = get_validator_object(v_address=c.v_address)
                    else:
                        # init tx
                        v = get_validator_by_contract_info(c_address=c_address, start_hash=start_hash)
                elif tx.type == C.TX_VALIDATOR_EDIT:
                    v_address, new_address, flag, sig_diff = tx.encoded_message()
                    v = get_validator_object(v_address=v_address)
                else:
                    log.error("Why include pre-unconfirmed? {}".format(tx))
                    continue
                # check upgradable
                signed_cks = get_signed_cks(tx)
                if v.require <= len(signed_cks & set(v.validators)):
                    del tx_builder.pre_unconfirmed[tx.hash]
                    if tx.hash in tx_builder.unconfirmed:
                        log.warning("Upgrade skip, already unconfirmed {}".format(tx))
                    else:
                        tx_builder.put_unconfirmed(tx=tx)
                        log.info("Upgrade pre-unconfirmed {}".format(tx))
            except Exception as e:
                log.debug("skip by '{}'".format(e), exc_info=True)

        # 2: sort and get txs to include in block
        unconfirmed_txs = [
            tx for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time)
            if tx.create_time < prune_limit
        ]
        if len(tx_builder.unconfirmed) != len(unconfirmed_txs):
            log.debug("prune too young tx [{}/{}]".format(len(unconfirmed_txs), len(tx_builder.unconfirmed)))

        # 3: remove unconfirmed outputs using txs
        limit_height = builder.best_block.height - C.MATURE_HEIGHT
        best_block, best_chain = builder.get_best_chain()
        for tx in unconfirmed_txs.copy():
            if tx.height is not None:
                unconfirmed_txs.remove(tx)  # already confirmed
                continue
            # inputs check
            for txhash, txindex in tx.inputs:
                input_tx = tx_builder.get_tx(txhash=txhash)
                if input_tx is None:
                    # not found input tx
                    unconfirmed_txs.remove(tx)
                    break
                elif input_tx.height is None:
                    # use unconfirmed tx's outputs
                    unconfirmed_txs.remove(tx)
                    break
                elif input_tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
                    if input_tx.height > limit_height:
                        # too young generated outputs
                        unconfirmed_txs.remove(tx)
                        break
                elif is_usedindex(
                        txhash=txhash,
                        txindex=txindex,
                        except_txhash=tx.hash,
                        best_block=best_block,
                        best_chain=best_chain):
                    # ERROR: already used outputs
                    unconfirmed_txs.remove(tx)
                    break
                else:
                    pass  # all ok

        # 4: prune oversize txs
        total_size = 80 + sum(tx.size for tx in unconfirmed_txs)
        for tx in sorted(unconfirmed_txs, key=lambda x: x.gas_price):
            if total_size < C.SIZE_BLOCK_LIMIT:
                break
            unconfirmed_txs.remove(tx)
            total_size -= tx.size

        # 5. check unconfirmed order
        errored_tx = check_unconfirmed_order(
            best_block=builder.best_block, ordered_unconfirmed_txs=unconfirmed_txs)
        if errored_tx is not None:
            # error is caused by remove tx of too few fee
            unconfirmed_txs = unconfirmed_txs[:unconfirmed_txs.index(errored_tx)]
            if errored_tx.hash in failed_txs:
                if 10 < failed_txs[errored_tx.hash]:
                    del tx_builder.unconfirmed[errored_tx.hash], failed_txs[errored_tx.hash]
                    log.warning('delete too many fail {}'.format(errored_tx))
                else:
                    failed_txs[errored_tx.hash] += 1
            else:
                failed_txs[errored_tx.hash] = 1
                log.warning('prune error tx {}'.format(errored_tx))

        # 6. update unconfirmed txs
        update_unconfirmed_txs(unconfirmed_txs)

    return ',  unconfirmed={}/{}/{} {}mS'.format(
        len(unconfirmed_txs), len(tx_builder.unconfirmed), len(tx_builder.pre_unconfirmed), int(
            (time() - s) * 1000))
