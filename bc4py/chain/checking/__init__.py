from bc4py.config import V, stream, BlockChainError
from bc4py.chain.checking.checkblock import check_block, check_block_time
from bc4py.chain.checking.checktx import check_tx, check_tx_time
from bc4py.chain.signature import fill_verified_addr_single
from bc4py.database.create import create_db
from bc4py.database.builder import chain_builder, account_builder
from logging import getLogger
from time import time
import asyncio

new_block_lock = asyncio.Lock()
log = getLogger('bc4py')


async def new_insert_block(block, f_time=True, f_sign=True):
    t = time()
    async with new_block_lock:
        fixed_delay = time() - t
        try:
            # Check
            if not block.pow_check():
                block.work2diff()
                block.target2diff()
                log.debug('reject, work check is failed. [{}<{}]'
                          .format(block.difficulty, block.work_difficulty))
                return False
            if f_time:
                check_block_time(block, fixed_delay)
            check_block(block)
            if f_sign:
                await fill_verified_addr_single(block)
            for tx in block.txs:
                check_tx(tx=tx, include_block=block)
                if f_time:
                    check_tx_time(tx)
            # Recode
            chain_builder.new_block(block)
            async with create_db(V.DB_ACCOUNT_PATH) as db:
                cur = await db.cursor()
                for tx in block.txs:
                    await account_builder.affect_new_tx(cur=cur, tx=tx)
                await db.commit()
            # insert database
            await chain_builder.batch_apply()
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
