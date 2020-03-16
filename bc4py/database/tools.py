from bc4py.config import C, BlockChainError
from bc4py.database import obj
from bc4py.database.account import read_all_pooled_address_set
from typing import AsyncGenerator

best_block_cache = None
best_chain_cache = None
target_address_cache = set()


def _get_best_chain_all(best_block):
    global best_block_cache, best_chain_cache
    # MemoryにおけるBestBlockまでのChainを返す
    if best_block is None:
        best_block_cache = best_chain_cache = None
        return obj.chain_builder.best_chain
    elif best_block_cache and best_block == best_block_cache:
        return best_chain_cache
    else:
        dummy, best_chain = obj.chain_builder.get_best_chain(best_block)
        # best_chain = [<height=n>, <height=n-1>,.. <height=n-m>]
        if len(best_chain) == 0:
            raise BlockChainError('Ignore, New block inserted on "_get_best_chain_all"')
        best_block_cache = best_block
        best_chain_cache = best_chain
        return best_chain


async def get_unspents_iter(target_address, best_block=None, best_chain=None) -> AsyncGenerator:
    if best_chain is None:
        best_chain = _get_best_chain_all(best_block)
    if best_chain is None:
        raise BlockChainError('Cannot get best_chain by {}'.format(best_block))
    allow_mined_height = best_chain[0].height - C.MATURE_HEIGHT
    # DataBaseより
    for address in target_address:
        for dummy, txhash, txindex, coin_id, amount, f_used in obj.tables.read_address_idx_iter(address):
            if f_used is False:
                if not is_unused_index(input_hash=txhash, input_index=txindex, best_block=best_block, best_chain=best_chain):
                    continue  # used
                tx = obj.tx_builder.get_account_tx(txhash)
                if tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD):
                    if tx.height is not None and tx.height < allow_mined_height:
                        yield address, tx.height, txhash, txindex, coin_id, amount
                else:
                    yield address, tx.height, txhash, txindex, coin_id, amount
    # Memoryより
    for block in reversed(best_chain):
        for tx in block.txs:
            for index, (address, coin_id, amount) in enumerate(tx.outputs):
                if not is_unused_index(input_hash=tx.hash, input_index=index, best_block=best_block, best_chain=best_chain):
                    continue  # used
                elif address in target_address:
                    if tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD):
                        if tx.height is not None and tx.height < allow_mined_height:
                            yield address, tx.height, tx.hash, index, coin_id, amount
                    else:
                        yield address, tx.height, tx.hash, index, coin_id, amount
    # Unconfirmedより
    if best_block is None:
        for tx in sorted(obj.tx_builder.unconfirmed.values(), key=lambda x: x.create_time):
            for index, (address, coin_id, amount) in enumerate(tx.outputs):
                if not is_unused_index(input_hash=tx.hash, input_index=index, best_block=best_block, best_chain=best_chain):
                    continue  # used
                elif address in target_address:
                    yield address, None, tx.hash, index, coin_id, amount
    # 返り値
    # address, height, txhash, index, coin_id, amount


async def get_my_unspents_iter(cur, best_chain=None) -> AsyncGenerator:
    last_uuid = len(target_address_cache)
    target_address_cache.update(await read_all_pooled_address_set(cur=cur, last_uuid=last_uuid))
    return get_unspents_iter(target_address=target_address_cache, best_block=None, best_chain=best_chain)


def get_output_from_input(input_hash, input_index, best_block=None, best_chain=None):
    """get OutputType from InputType"""
    assert obj.chain_builder.best_block, 'Not Tables init'
    if best_chain is None:
        best_chain = _get_best_chain_all(best_block)

    # check database
    pair = obj.tables.read_unused_index(input_hash, input_index)
    if pair is not None:
        return pair

    # check memory
    for block in best_chain:
        for tx in block.txs:
            if tx.hash == input_hash:
                if input_index < len(tx.outputs):
                    return tx.outputs[input_index]

    # check unconfirmed
    if best_block is None:
        for tx in list(obj.tx_builder.unconfirmed.values()):
            if tx.hash == input_hash:
                if input_index < len(tx.outputs):
                    return tx.outputs[input_index]

    # not found
    return None


def is_unused_index(input_hash, input_index, best_block=None, best_chain=None) -> bool:
    """check inputs is unused(True) or not(False)"""
    assert obj.chain_builder.best_block, 'Not Tables init'
    if best_chain is None:
        best_chain = _get_best_chain_all(best_block)
    is_unused = False

    # check database
    if obj.tables.read_unused_index(input_hash, input_index) is not None:
        is_unused = True

    # check memory
    for block in best_chain:
        if best_block and block == best_block:
            continue  # do not check best_block when specified
        for tx in block.txs:
            if tx.hash == input_hash:
                if input_index < len(tx.outputs):
                    is_unused = True
            for txhash, txindex in tx.inputs:
                if txhash == input_hash and txindex == input_index:
                    return False

    # check unconfirmed
    if best_block is None:
        for tx in obj.tx_builder.unconfirmed.values():
            if tx.hash == input_hash:
                if input_index < len(tx.outputs):
                    is_unused = True
            for txhash, txindex in tx.inputs:
                if txhash == input_hash and txindex == input_index:
                    return False

    # all check passed
    return is_unused


def is_unused_index_except_me(input_hash, input_index, except_hash, best_block, best_chain) -> bool:
    """check inputs is unused(True) or not(False)
    WARNING: except hash work on memory or unconfirmed status
    """
    assert obj.chain_builder.best_block, 'Not Tables init'
    is_unused = False

    # check database
    if obj.tables.read_unused_index(input_hash, input_index) is not None:
        is_unused = True

    # check memory
    for block in best_chain:
        if block == best_block:
            continue
        for tx in block.txs:
            if tx.hash == except_hash:
                continue
            if input_index < len(tx.outputs):
                is_unused = True
            for txhash, txindex in tx.inputs:
                if txhash == input_hash and txindex == input_index:
                    return False

    # check unconfirmed
    for tx in list(obj.tx_builder.unconfirmed.values()):
        if tx.hash == except_hash:
            continue
        if input_index < len(tx.outputs):
            is_unused = True
        for txhash, txindex in tx.inputs:
            if txhash == input_hash and txindex == input_index:
                return False

    # all check passed
    return is_unused


__all__ = [
    "get_unspents_iter",
    "get_my_unspents_iter",
    "get_output_from_input",
    "is_unused_index",
    "is_unused_index_except_me",
]
