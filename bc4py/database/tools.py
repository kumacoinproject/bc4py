from bc4py.config import C, V, BlockChainError
from bc4py.chain.mintcoin import MintCoinObject, setup_base_currency_mint, MintCoinError
from bc4py.database.builder import builder, tx_box, user_account
from bc4py.database.create import closing, create_db
from bc4py.contract.storage import ContractStorage
import bjson


def _get_best_chain_all(best_block):
    # MemoryにおけるBestBlockまでのChainを返す
    if best_block:
        block = best_block
        best_chain = list()
        while block.f_on_memory:
            best_chain.append(block)
            block = builder.get_block(block.previous_hash)
    else:
        best_block, best_chain = builder.get_best_chain()
    # best_chain = [<height=n>, <height=n-1>,.. <height=n-m>]
    return best_chain


def get_mintcoin(mint_id, best_block=None):
    if mint_id < 0:
        raise MintCoinError('coinID is more than 0.')
    elif mint_id == 0:
        return setup_base_currency_mint()
    mint_coin_old = None
    # DataBaseより
    for dummy, index, txhash in builder.db.get_coins_iter(mint_id):
        binary = tx_box.get_tx(txhash).message
        mint_coin_new = MintCoinObject(txhash=txhash, binary=binary)
        mint_coin_new.marge(mint_coin_old)
        mint_coin_new.check_param()
        mint_coin_new.check_sign()
        mint_coin_old = mint_coin_new
    # Memoryより
    best_chain = _get_best_chain_all(best_block)
    for block in reversed(best_chain):
        for tx in block.txs:
            if tx.type != C.TX_MINT_COIN:
                continue
            mint_coin_new = MintCoinObject(txhash=tx.hash, binary=tx.message)
            mint_coin_new.marge(mint_coin_old)
            mint_coin_new.check_param()
            mint_coin_new.check_sign()
            mint_coin_old = mint_coin_new
    # Unconfirmedより
    if best_block is None:
        for tx in sorted(tx_box.unconfirmed, key=lambda x: x.time):
            if tx.type != C.TX_MINT_COIN:
                continue
            mint_coin_new = MintCoinObject(txhash=tx.hash, binary=tx.message)
            mint_coin_new.marge(mint_coin_old)
            mint_coin_new.check_param()
            mint_coin_new.check_sign()
            mint_coin_old = mint_coin_new
    return mint_coin_old


def get_contract_storage(c_address, best_block=None):
    # DataBaseより
    cs = ContractStorage()
    for dummy, index, start_hash, finish_hash in builder.db.get_contract_iter(c_address):
        if index == 0:
            start_tx = tx_box.get_tx(start_hash)
            dummy, c_bin, c_cs = bjson.loads(start_tx.message)
            cs.key_value = c_cs or dict()  # TODO:初期値設定
        else:
            finish_tx = tx_box.get_tx(finish_hash)
            c_status, dummy, c_diff = bjson.loads(finish_tx.message)
            cs.marge(c_diff)
    # Memoryより
    best_chain = _get_best_chain_all(best_block)
    for block in reversed(best_chain):
        for tx in block.txs:
            if tx.type == C.TX_CREATE_CONTRACT:
                dummy, c_bin, c_cs = bjson.loads(tx.message)
                cs.key_value = c_cs or dict()  # TODO:初期値設定
            if tx.type == C.TX_START_CONTRACT:
                pass
            elif tx.type == C.TX_FINISH_CONTRACT:
                c_status, dummy, c_diff = bjson.loads(tx.message)
                cs.marge(c_diff)
            else:
                pass
    # Unconfirmedより
    if best_block is None:
        for tx in sorted(tx_box.unconfirmed, key=lambda x: x.time):
            if tx.type == C.TX_CREATE_CONTRACT:
                dummy, c_bin, c_cs = bjson.loads(tx.message)
                cs.key_value = c_cs or dict()  # TODO:初期値設定
            if tx.type == C.TX_START_CONTRACT:
                pass
            elif tx.type == C.TX_FINISH_CONTRACT:
                c_status, dummy, c_diff = bjson.loads(tx.message)
                cs.marge(c_diff)
            else:
                pass
    return cs


def get_tx_with_usedindex(txhash, best_block=None):
    # DataBaseより
    used = set(builder.db.get_tx(txhash).used_index)
    # Memoryより
    best_chain = _get_best_chain_all(best_block)
    for block in reversed(best_chain):
        for _tx in block.txs:
            for _txhash, _txindex in _tx.inputs:
                if txhash == _txhash:
                    used.add(_txindex)
    # Unconfirmedより
    if best_block is None:
        for _tx in sorted(tx_box.unconfirmed, key=lambda x: x.time):
            for _txhash, _txindex in _tx.inputs:
                if txhash == _txhash:
                    used.add(_txindex)
    tx = tx_box.get_tx(txhash)
    tx.used_index = bytes(sorted(used))
    return tx


def get_utxo_iter(target_address, best_block=None):
    best_chain = _get_best_chain_all(best_block)
    best_block_tmp = best_chain[0]
    allow_mined_height = best_block_tmp.height - C.MATURE_HEIGHT
    # DataBaseより
    for address in target_address:
        for dummy, txhash, txindex, coin_id, amount, f_used in builder.db.get_address_iter(address):
            if f_used is False:
                tx = get_tx_with_usedindex(txhash, best_block)
                if txindex in tx.used_index:
                    continue  # Used
                elif tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD) and tx.height < allow_mined_height:
                    yield address, tx.height, txhash, txindex, coin_id, amount
                else:
                    yield address, tx.height, txhash, txindex, coin_id, amount
                assert txindex not in tx.used_index, 'TXIndex is used!? {}:{}'.format(tx, txindex)
    # Memoryより
    for block in reversed(best_chain):
        for tx in block.txs:
            used_index = get_tx_with_usedindex(tx.hash, best_block).used_index
            for index, (address, coin_id, amount) in enumerate(tx.outputs):
                if index in used_index:
                    continue  # Used
                elif address in target_address:
                    if tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD) and tx.height < allow_mined_height:
                        yield address, tx.height, tx.hash, index, coin_id, amount
                    else:
                        yield address, tx.height, tx.hash, index, coin_id, amount
    # Unconfirmedより
    if best_block is None:
        for tx in sorted(tx_box.unconfirmed, key=lambda x: x.time):
            used_index = get_tx_with_usedindex(tx.hash).used_index
            for index, (address, coin_id, amount) in enumerate(tx.outputs):
                if index in used_index:
                    continue  # Used
                elif address in target_address:
                    yield address, None, tx.hash, index, coin_id, amount
    # 返り値
    # address, height, txhash, index, coin_id, amount


def get_unspents_iter():
    target_address = set()
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        cur.execute("SELECT `ck` FROM `pool`")
        for (address,) in cur:
            target_address.add(address)
    return get_utxo_iter(target_address)


__all__ = [
    "get_mintcoin",
    "get_contract_storage",
    "get_tx_with_usedindex",
    "get_unspents_iter"
]
