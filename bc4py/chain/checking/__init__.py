from bc4py.config import V, P, stream, BlockChainError
from bc4py.chain.checking.checkblock import check_block, check_block_time
from bc4py.chain.checking.checktx import check_tx, check_tx_time
from bc4py.chain.signature import fill_verified_addr_single
from bc4py.database.builder import builder, user_account
import threading
from time import time
from logging import getLogger


new_block_lock = threading.Lock()
log = getLogger('bc4py')


def new_insert_block(block, f_time=True, f_sign=True):
    t = time()
    with new_block_lock:
        fixed_delay = time() - t
        try:
            # Check
            if f_time:
                check_block_time(block, fixed_delay)
            check_block(block)
            if f_sign:
                fill_verified_addr_single(block)
            for tx in block.txs:
                check_tx(tx=tx, include_block=block)
                if f_time:
                    check_tx_time(tx)
            # Recode
            builder.new_block(block)
            for tx in block.txs:
                user_account.affect_new_tx(tx)
            # insert database
            builder.batch_apply()
            # inner streaming
            if not stream.is_disposed:
                stream.on_next(block)
            log.info("check success {}Sec {}".format(round(time() - t, 3), block))
            return True
        except BlockChainError as e:
            log.warning("Reject new block by \"{}\"".format(e), exc_info=True)
            log.debug("Reject block => {}".format(block.getinfo()))
            return False
        except Exception as e:
            message = "New insert block error, \"{}\"".format(e)
            log.warning(message, exc_info=True)
            return False


__all__ = [
    "new_insert_block",
    "check_block",
    "check_block_time",
    "check_tx",
    "check_tx_time",
]
