from bc4py.config import C, V
from bc4py.database.builder import chain_builder, tx_builder
from bc4py.database.tools import is_usedindex
from bc4py.chain.checking.checktx import check_unconfirmed_order
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
        while chain_builder.best_block is None:
            sleep(0.2)
        update_previous_block(chain_builder.best_block)
        return ',  height={}'.format(chain_builder.best_block.height + 1)


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
        # CODE REMOVED

        # 2: sort and get txs to include in block
        unconfirmed_txs = sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time)

        # 3: remove unconfirmed outputs using txs
        limit_height = chain_builder.best_block.height - C.MATURE_HEIGHT
        best_block, best_chain = chain_builder.get_best_chain()
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

        # TODO: オーダーをチェック＆依存関係をキャッシュ化する

        # 5. check unconfirmed order
        #errored_tx = check_unconfirmed_order(
        #    best_block=chain_builder.best_block, ordered_unconfirmed_txs=unconfirmed_txs)
        #if errored_tx is not None:
        #    # error is caused by remove tx of too few fee
        #    unconfirmed_txs = unconfirmed_txs[:unconfirmed_txs.index(errored_tx)]
        #    if errored_tx.hash in failed_txs:
        #        if 10 < failed_txs[errored_tx.hash]:
        #            del tx_builder.unconfirmed[errored_tx.hash], failed_txs[errored_tx.hash]
        #            log.warning('delete too many fail {}'.format(errored_tx))
        #        else:
        #            failed_txs[errored_tx.hash] += 1
        #    else:
        #        failed_txs[errored_tx.hash] = 1
        #        log.warning('prune error tx {}'.format(errored_tx))

        # 6. update unconfirmed txs
        update_unconfirmed_txs(unconfirmed_txs)

    return ',  unconfirmed={} {}mS'.format(
        len(unconfirmed_txs), int((time() - s) * 1000))
