from bc4py.config import C, BlockChainError
from bc4py.database.builder import chain_builder, tx_builder
from bc4py.database.account import read_all_pooled_address
from time import sleep

best_block_cashe = None
best_chain_cashe = None


def _get_best_chain_all(best_block):
    global best_block_cashe, best_chain_cashe
    # MemoryにおけるBestBlockまでのChainを返す
    if best_block is None:
        best_block_cashe = best_chain_cashe = None
        return chain_builder.best_chain
    elif best_block_cashe and best_block == best_block_cashe:
        return best_chain_cashe
    else:
        dummy, best_chain = chain_builder.get_best_chain(best_block)
        # best_chain = [<height=n>, <height=n-1>,.. <height=n-m>]
        if len(best_chain) == 0:
            raise BlockChainError('Ignore, New block inserted on "_get_best_chain_all"')
        best_block_cashe = best_block
        best_chain_cashe = best_chain
        return best_chain


def get_unspents_iter(target_address, best_block=None, best_chain=None):
    failed = 0
    while failed < 20:
        if best_chain is None:
            best_chain = _get_best_chain_all(best_block)
        if best_chain:
            break
        failed += 1
        sleep(0.05)
    else:
        raise BlockChainError('Cannot get best_chain by {}'.format(best_block))
    allow_mined_height = best_chain[0].height - C.MATURE_HEIGHT
    # DataBaseより
    for address in target_address:
        for dummy, txhash, txindex, coin_id, amount, f_used in chain_builder.db.read_address_idx_iter(address):
            if f_used is False:
                if txindex in get_usedindex(txhash=txhash, best_block=best_block, best_chain=best_chain):
                    continue  # Used
                tx = tx_builder.get_tx(txhash)
                if tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD):
                    if tx.height is not None and tx.height < allow_mined_height:
                        yield address, tx.height, txhash, txindex, coin_id, amount
                else:
                    yield address, tx.height, txhash, txindex, coin_id, amount
    # Memoryより
    for block in reversed(best_chain):
        for tx in block.txs:
            used_index = get_usedindex(txhash=tx.hash, best_block=best_block, best_chain=best_chain)
            for index, (address, coin_id, amount) in enumerate(tx.outputs):
                if index in used_index:
                    continue  # Used
                elif address in target_address:
                    if tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD):
                        if tx.height is not None and tx.height < allow_mined_height:
                            yield address, tx.height, tx.hash, index, coin_id, amount
                    else:
                        yield address, tx.height, tx.hash, index, coin_id, amount
    # Unconfirmedより
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time):
            used_index = get_usedindex(txhash=tx.hash, best_block=best_block, best_chain=best_chain)
            for index, (address, coin_id, amount) in enumerate(tx.outputs):
                if index in used_index:
                    continue  # Used
                elif address in target_address:
                    yield address, None, tx.hash, index, coin_id, amount
    # 返り値
    # address, height, txhash, index, coin_id, amount


def get_my_unspents_iter(cur, best_chain=None):
    target_address = read_all_pooled_address(cur=cur)
    yield from get_unspents_iter(target_address=target_address, best_block=None, best_chain=best_chain)


def get_usedindex(txhash, best_block=None, best_chain=None):
    assert chain_builder.best_block, 'Not DataBase init'
    if best_chain is None:
        best_chain = _get_best_chain_all(best_block)
    # Memoryより
    usedindex = set()
    for block in best_chain:
        if best_block and block == best_block:
            continue
        for tx in block.txs:
            for _txhash, _txindex in tx.inputs:
                if _txhash == txhash:
                    usedindex.add(_txindex)
    # DataBaseより
    usedindex.update(chain_builder.db.read_usedindex(txhash))
    # unconfirmedより
    if best_block is None:
        for tx in list(tx_builder.unconfirmed.values()):
            for _txhash, _txindex in tx.inputs:
                if _txhash == txhash:
                    usedindex.add(_txindex)
    return usedindex


def is_usedindex(txhash, txindex, except_txhash, best_block=None, best_chain=None):
    assert chain_builder.best_block, 'Not DataBase init'
    if best_chain is None:
        best_chain = _get_best_chain_all(best_block)
    # Memoryより
    for block in best_chain:
        for tx in block.txs:
            if tx.hash == except_txhash:
                continue
            for _txhash, _txindex in tx.inputs:
                if _txhash == txhash and _txindex == txindex:
                    return True
    # DataBaseより
    if txindex in chain_builder.db.read_usedindex(txhash):
        return True
    # unconfirmedより
    if best_block is None:
        for tx in tx_builder.unconfirmed.values():
            if tx.hash == except_txhash:
                continue
            for _txhash, _txindex in tx.inputs:
                if _txhash == txhash and _txindex == txindex:
                    return True
    return False


__all__ = [
    "get_unspents_iter",
    "get_my_unspents_iter",
    "get_usedindex",
    "is_usedindex",
]
