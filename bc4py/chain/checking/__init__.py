from bc4py.config import P, BlockChainError
from bc4py.chain.checking.checkblock import check_block, check_block_time
from bc4py.chain.checking.checktx import check_tx, check_tx_time
from bc4py.database.builder import builder, user_account
import threading
import time
import logging
from collections import deque

global_lock = threading.Lock()
failed_deque = deque([], maxlen=10)


def add_failed_mark():
    failed_deque.append(time.time())
    if min(failed_deque) < time.time() - 3600:
        return
    elif len(failed_deque) >= 10:
        builder.make_failemark("Too many block check fail.")
        failed_deque.clear()
        P.F_NOW_BOOTING = True


def new_insert_block(block, time_check=False):
    t = time.time()
    with global_lock:
        fixed_delay = time.time() - t
        try:
            # Check
            if time_check:
                check_block_time(block, fixed_delay)
            check_block(block)
            for tx in block.txs:
                check_tx(tx=tx, include_block=block)
                if time_check:
                    check_tx_time(tx)
            # Recode
            builder.new_block(block)
            for tx in block.txs:
                user_account.affect_new_tx(tx)
            builder.batch_apply()
            # WebSocket apiに通知
            if P.NEW_CHAIN_INFO_QUE:
                P.NEW_CHAIN_INFO_QUE.put_nowait(('block', block.getinfo()))
            logging.info("New block accepted {}Sec {}.".format(round(time.time()-t, 3), block))
            return True
        except BlockChainError as e:
            logging.warning("Reject new block by \"{}\"".format(e))
            delay = time.time() - builder.best_block.time
            if delay > 10800:  # 3hours
                logging.warning("{}Min before block inserted, too old on DB!".format(delay//60))
                P.F_NOW_BOOTING = True
            return False
        except BaseException as e:
            message = "New insert block error, \"{}\"".format(e)
            logging.warning(message, exc_info=True)
            add_failed_mark()
            return False


__all__ = [
    "new_insert_block",
    "check_block", "check_block_time",
    "check_tx", "check_tx_time"
]
