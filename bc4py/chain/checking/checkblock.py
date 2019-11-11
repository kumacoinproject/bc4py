from bc4py.config import C, V, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.difficulty import get_bits_by_hash
from bc4py.database.builder import chain_builder
from logging import getLogger
from time import time

log = getLogger('bc4py')


def check_block(block: Block):
    # 挿入前にBlockの正当性チェック
    if len(block.txs) == 0:
        raise BlockChainError('Block don\'t have any txs')
    elif block.size > C.SIZE_BLOCK_LIMIT:
        raise BlockChainError('Block size is too large [{}b>{}b]'.format(block.size, C.SIZE_BLOCK_LIMIT))
    bits = get_bits_by_hash(previous_hash=block.previous_hash, consensus=block.flag)[0]
    if block.bits != bits:
        raise BlockChainError('Block bits differ from calc. [{}!={}]'.format(block.bits, bits))
    log.debug("check block success {}".format(block))


def check_block_time(block: Block, fix_delay):
    # 新規受け入れ時のみ検査
    delay = int(time() - fix_delay) - block.create_time
    create_time = block.create_time - V.BLOCK_GENESIS_TIME
    if C.ACCEPT_MARGIN_TIME < abs(block.time - create_time):
        raise BlockChainError('Block time is out of range [{}<{}-{}={},{}]'.format(
            C.ACCEPT_MARGIN_TIME, block.time, create_time, block.time - create_time, delay))
    if C.ACCEPT_MARGIN_TIME < delay:
        log.warning("Long delay, for check new block. [{}<{}]".format(C.ACCEPT_MARGIN_TIME, delay))
    if block.flag != C.BLOCK_GENESIS:
        previous_block = chain_builder.get_block(blockhash=block.previous_hash)
        if previous_block is None:
            raise BlockChainError('cannot find previous block height={}'.format(block.height))
        if previous_block.time >= block.time:
            raise BlockChainError('block time warp not allowed previous={} new={}'
                                  .format(previous_block.time, block.time))
    log.debug("check block time success {}".format(block))
