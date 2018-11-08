from bc4py.config import C, V, BlockChainError
from bc4py.chain.mintcoin import MintCoinObject, setup_base_currency_mint, MintCoinError
from bc4py.database.builder import builder, tx_builder
from bc4py.database.create import closing, create_db
from bc4py.contract.storage import ContractStorage
from bc4py.contract.tools import contract2binary
from bc4py.contract.c_validator import Contract
from bc4py.database.account import read_pooled_address_iter
import bjson


best_block_cashe = None
best_chain_cashe = None


def _get_best_chain_all(best_block):
    global best_block_cashe, best_chain_cashe
    # MemoryにおけるBestBlockまでのChainを返す
    if best_block is None:
        best_block_cashe = best_chain_cashe = None
        return builder.best_chain
    elif best_block_cashe and best_block == best_block_cashe:
        return best_chain_cashe
    else:
        dummy, best_chain = builder.get_best_chain(best_block)
        # best_chain = [<height=n>, <height=n-1>,.. <height=n-m>]
        if len(best_chain) == 0:
            raise BlockChainError('Ignore, New block inserted on "_get_best_chain_all".')
        best_block_cashe = best_block
        best_chain_cashe = best_chain
        return best_chain


def get_mintcoin(mint_id, best_block=None, best_chain=None):
    if mint_id < 0:
        raise MintCoinError('coinID is more than 0.')
    elif mint_id == 0:
        return setup_base_currency_mint()
    mint_coin_old = None
    # DataBaseより
    for dummy, index, txhash in builder.db.read_coins_iter(mint_id):
        binary = tx_builder.get_tx(txhash).message
        mint_coin_new = MintCoinObject(txhash, binary)
        if mint_coin_new.coin_id != mint_id:
            continue
        mint_coin_new.marge(mint_coin_old)
        mint_coin_new.check_param()
        mint_coin_new.check_sign()
        mint_coin_old = mint_coin_new
    # Memoryより
    best_chain = best_chain or _get_best_chain_all(best_block)
    for block in reversed(best_chain):
        for tx in block.txs:
            if tx.type != C.TX_MINT_COIN:
                continue
            mint_coin_new = MintCoinObject(txhash=tx.hash, binary=tx.message)
            if mint_coin_new.coin_id != mint_id:
                continue
            mint_coin_new.marge(mint_coin_old)
            mint_coin_new.check_param()
            mint_coin_new.check_sign()
            mint_coin_old = mint_coin_new
    # Unconfirmedより
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            if tx.type != C.TX_MINT_COIN:
                continue
            mint_coin_new = MintCoinObject(txhash=tx.hash, binary=tx.message)
            if mint_coin_new.coin_id != mint_id:
                continue
            mint_coin_new.marge(mint_coin_old)
            mint_coin_new.check_param()
            mint_coin_new.check_sign()
            mint_coin_old = mint_coin_new
    return mint_coin_old


"""def get_contract_binary(c_address, best_block=None, best_chain=None):
    assert V.CONTRACT_VALIDATOR_ADDRESS, 'Not found validator address.'
    if c_address == V.CONTRACT_VALIDATOR_ADDRESS:
        return contract2binary(Contract)
    # DataBaseより
    for dummy, index, start_hash, finish_hash in builder.db.read_contract_iter(c_address):
        start_tx = tx_builder.get_tx(start_hash)
        dummy, c_bin, c_cs = bjson.loads(start_tx.message)
        return c_bin
    # Memoryより
    best_chain = best_chain or _get_best_chain_all(best_block)
    for block in reversed(best_chain):
        for tx in block.txs:
            if tx.type == C.TX_CREATE_CONTRACT:
                dummy, c_bin, c_cs = bjson.loads(tx.message)
                return c_bin
    # Unconfirmedより
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            if tx.type == C.TX_CREATE_CONTRACT:
                dummy, c_bin, c_cs = bjson.loads(tx.message)
                return c_bin
    return None"""


"""def get_validator_info(best_block=None, best_chain=None):
    assert V.CONTRACT_VALIDATOR_ADDRESS, 'Not found validator address.'
    cs = get_contract_storage(V.CONTRACT_VALIDATOR_ADDRESS, best_block, best_chain)
    validator_cks = set()
    for ck, uuid in cs.items():
        if len(ck) != 40:
            continue
        elif cs.get(b'\x00' + uuid, b'\x00') == b'\x01':
            validator_cks.add(ck.decode())
    required_num = len(validator_cks) * 3 // 4 + 1
    return validator_cks, required_num"""


"""def get_contract_history_iter(c_address, best_block=None, best_chain=None):
    # DataBaseより
    last_index = 0
    for dummy, index, start_hash, finish_hash in builder.db.read_contract_iter(c_address):
        yield index, start_hash, finish_hash, None, False
        last_index += 1
    # Memoryより
    best_chain = best_chain or _get_best_chain_all(best_block)
    for block in reversed(best_chain):
        for tx in block.txs:
            if tx.type == C.TX_CREATE_CONTRACT:
                c_address2, c_bin, c_cs = bjson.loads(tx.message)
                if c_address == c_address2:
                    yield 0, tx.hash, b'\x00'*32, tx.height, True
                    last_index += 1
            elif tx.type == C.TX_START_CONTRACT:
                c_address2, c_method, c_args, c_redeem = bjson.loads(tx.message)
                if c_address != c_address2:
                    continue
                for finish_tx in block.txs:
                    if finish_tx.type != C.TX_FINISH_CONTRACT:
                        continue
                    dummy0, start_hash, dummy1 = bjson.loads(finish_tx.message)
                    if start_hash == tx.hash:
                        yield last_index, start_hash, finish_tx.hash, tx.height, True
                        last_index += 1
                        break
    # Unconfirmedより
    if best_block is None:
        validator_cks, required_num = get_validator_info()
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            if tx.type == C.TX_CREATE_CONTRACT:
                yield 0, tx.hash, b'\x00'*32, None, True
                last_index += 1
            if tx.type == C.TX_START_CONTRACT:
                c_address2, c_method, c_args, c_redeem = bjson.loads(tx.message)
                if c_address != c_address2:
                    continue
                for finish_tx in tx_builder.unconfirmed.values():
                    if len(finish_tx.signature) < required_num:
                        continue
                    elif finish_tx.type != C.TX_FINISH_CONTRACT:
                        continue
                    dummy0, start_hash, dummy1 = bjson.loads(finish_tx.message)
                    if start_hash == tx.hash:
                        yield last_index, start_hash, finish_tx.hash, None, True
                        last_index += 1
                        break
    # index, start_hash, finish_hash, height, on_memory"""


"""def get_contract_storage(c_address, best_block=None, best_chain=None):
    # DataBaseより
    cs = ContractStorage()
    for dummy, index, start_hash, finish_hash in builder.db.read_contract_iter(c_address):
        if index == 0:
            start_tx = tx_builder.get_tx(start_hash)
            dummy, c_bin, c_cs = bjson.loads(start_tx.message)
            cs.key_value = c_cs or dict()
        else:
            finish_tx = tx_builder.get_tx(finish_hash)
            c_status, dummy, c_diff = bjson.loads(finish_tx.message)
            cs.marge(c_diff)
    # Memoryより
    best_chain = best_chain or _get_best_chain_all(best_block)
    for block in reversed(best_chain):
        for tx in block.txs:
            if tx.type == C.TX_CREATE_CONTRACT:
                check_address, c_bin, c_cs = bjson.loads(tx.message)
                if c_address == check_address:
                    cs.key_value = c_cs or dict()
            elif tx.type == C.TX_START_CONTRACT:
                pass
            elif tx.type == C.TX_FINISH_CONTRACT:
                c_status, start_hash, c_diff = bjson.loads(tx.message)
                start_tx = tx_builder.get_tx(start_hash)
                check_address, c_bin, c_cs = bjson.loads(start_tx.message)
                if c_address == check_address:
                    cs.marge(c_diff)
    # Unconfirmedより
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            if tx.type == C.TX_CREATE_CONTRACT:
                check_address, c_bin, c_cs = bjson.loads(tx.message)
                cs.key_value = c_cs or dict()
            elif tx.type == C.TX_START_CONTRACT:
                pass
            elif tx.type == C.TX_FINISH_CONTRACT:
                c_status, start_hash, c_diff = bjson.loads(tx.message)
                start_tx = tx_builder.get_tx(start_hash)
                check_address, c_bin, c_cs = bjson.loads(start_tx.message)
                if c_address == check_address:
                    cs.marge(c_diff)
    return cs"""


def get_utxo_iter(target_address, best_block=None, best_chain=None):
    assert isinstance(target_address, set), 'TargetAddress is set.'
    best_chain = best_chain or _get_best_chain_all(best_block)
    allow_mined_height = best_chain[0].height - C.MATURE_HEIGHT
    # DataBaseより
    for address in target_address:
        for dummy, txhash, txindex, coin_id, amount, f_used in builder.db.read_address_idx_iter(address):
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
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            used_index = get_usedindex(txhash=tx.hash, best_block=best_block, best_chain=best_chain)
            for index, (address, coin_id, amount) in enumerate(tx.outputs):
                if index in used_index:
                    continue  # Used
                elif address in target_address:
                    yield address, None, tx.hash, index, coin_id, amount
    # 返り値
    # address, height, txhash, index, coin_id, amount


def get_unspents_iter(outer_cur=None, best_chain=None):
    target_address = set()
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = outer_cur or db.cursor()
        for (uuid, address, user) in read_pooled_address_iter(cur):
            target_address.add(address)
    return get_utxo_iter(target_address=target_address, best_block=None, best_chain=best_chain)


def get_usedindex(txhash, best_block=None, best_chain=None):
    assert builder.best_block, 'Not DataBase init.'
    best_chain = best_chain or _get_best_chain_all(best_block)
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
    usedindex.update(builder.db.read_usedindex(txhash))
    # unconfirmedより
    if best_block is None:
        for tx in list(tx_builder.unconfirmed.values()):
            for _txhash, _txindex in tx.inputs:
                if _txhash == txhash:
                    usedindex.add(_txindex)
    return usedindex


def is_usedindex(txhash, txindex, except_txhash, best_block=None, best_chain=None):
    assert builder.best_block, 'Not DataBase init.'
    best_chain = best_chain or _get_best_chain_all(best_block)
    # Memoryより
    for block in best_chain:
        for tx in block.txs:
            if tx.hash == except_txhash:
                continue
            for _txhash, _txindex in tx.inputs:
                if _txhash == txhash and _txindex == txindex:
                    return True
    # DataBaseより
    if txindex in builder.db.read_usedindex(txhash):
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
    "get_mintcoin",
    # "get_contract_binary",
    # "get_validator_info",
    # "get_contract_history_iter",
    # "get_contract_storage",
    "get_utxo_iter",
    "get_unspents_iter",
    "get_usedindex",
    "is_usedindex"
]
