from bc4py.config import C, V, BlockChainError
from bc4py.chain.mintcoin import MintCoinObject, setup_base_currency_mint, MintCoinError
from bc4py.database.builder import builder, tx_builder, user_account
from bc4py.database.create import closing, create_db
from bc4py.contract.storage import ContractStorage
from bc4py.user import UserCoins, CoinObject
from bc4py.database.account import insert_log, read_pooled_address_iter
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
        best_chain = builder.best_chain
    # best_chain = [<height=n>, <height=n-1>,.. <height=n-m>]
    return best_chain


def get_mintcoin(mint_id, best_block=None):
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
    best_chain = _get_best_chain_all(best_block)
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


def get_contract_binary(c_address, best_block=None):
    # DataBaseより
    for dummy, index, start_hash, finish_hash in builder.db.read_contract_iter(c_address):
        start_tx = tx_builder.get_tx(start_hash)
        dummy, c_bin, c_cs = bjson.loads(start_tx.message)
        return c_bin
    # Memoryより
    best_chain = _get_best_chain_all(best_block)
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
    return None


def get_validator_info(best_block=None):
    assert V.CONTRACT_VALIDATOR_ADDRESS, 'Not found validator address.'
    cs = get_contract_storage(V.CONTRACT_VALIDATOR_ADDRESS, best_block)
    validator_cks = set()
    for k, v in cs.items():
        cmd, address = k[0], k[1:].decode()
        if cmd != 0:
            pass
        elif v == b'\x01':
            validator_cks.add(address)
    required_num = len(validator_cks) * 3 // 4 + 1
    return validator_cks, required_num


def get_contract_history_iter(c_address, best_block=None):
    # DataBaseより
    last_index = 0
    for dummy, index, start_hash, finish_hash in builder.db.read_contract_iter(c_address):
        yield index, start_hash, finish_hash, False
        last_index = index
    # Memoryより
    best_chain = _get_best_chain_all(best_block)
    for block in reversed(best_chain):
        for tx in block.txs:
            if tx.type == C.TX_CREATE_CONTRACT:
                yield 0, tx.hash, b'\x00'*32, False
            elif tx.type == C.TX_START_CONTRACT:
                last_index += 1
                for finish_tx in block.txs:
                    dummy0, start_hash, dummy1 = bjson.loads(finish_tx.message)
                    if start_hash == tx.hash:
                        yield last_index, start_hash, finish_tx.hash, False
                        break
    # Unconfirmedより
    if best_block is None:
        validator_cks, required_num = get_validator_info()
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            if tx.type == C.TX_CREATE_CONTRACT:
                yield 0, tx.hash, b'\x00'*32, True
            if tx.type == C.TX_START_CONTRACT:
                last_index += 1
                for finish_tx in tx_builder.unconfirmed.values():
                    if len(finish_tx.signature) < required_num:
                        continue
                    dummy0, start_hash, dummy1 = bjson.loads(finish_tx.message)
                    if start_hash == tx.hash:
                        yield last_index, start_hash, finish_tx.hash, True
                        break


def get_contract_storage(c_address, best_block=None):
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
    best_chain = _get_best_chain_all(best_block)
    for block in reversed(best_chain):
        for tx in block.txs:
            if tx.type == C.TX_CREATE_CONTRACT:
                dummy, c_bin, c_cs = bjson.loads(tx.message)
                cs.key_value = c_cs or dict()
            if tx.type == C.TX_START_CONTRACT:
                pass
            elif tx.type == C.TX_FINISH_CONTRACT:
                c_status, dummy, c_diff = bjson.loads(tx.message)
                cs.marge(c_diff)
    # Unconfirmedより
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            if tx.type == C.TX_CREATE_CONTRACT:
                dummy, c_bin, c_cs = bjson.loads(tx.message)
                cs.key_value = c_cs or dict()
            if tx.type == C.TX_START_CONTRACT:
                pass
            elif tx.type == C.TX_FINISH_CONTRACT:
                c_status, dummy, c_diff = bjson.loads(tx.message)
                cs.marge(c_diff)
    return cs


def get_utxo_iter(target_address, best_block=None):
    assert isinstance(target_address, set), 'TargetAddress is set.'
    best_chain = _get_best_chain_all(best_block)
    allow_mined_height = best_chain[0].height - C.MATURE_HEIGHT
    # DataBaseより
    for address in target_address:
        for dummy, txhash, txindex, coin_id, amount, f_used in builder.db.read_address_idx_iter(address):
            if f_used is False:
                if txindex in tx_builder.get_usedindex(txhash, best_block):
                    continue  # Used
                tx = tx_builder.get_tx(txhash)
                if tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD) and tx.height < allow_mined_height:
                    yield address, tx.height, txhash, txindex, coin_id, amount
                else:
                    yield address, tx.height, txhash, txindex, coin_id, amount
    # Memoryより
    for block in reversed(best_chain):
        for tx in block.txs:
            used_index = tx_builder.get_usedindex(tx.hash, best_block)
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
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            used_index = tx_builder.get_usedindex(tx.hash)
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
        for (uuid, address, user) in read_pooled_address_iter(db.cursor()):
            target_address.add(address)
    return get_utxo_iter(target_address)


__all__ = [
    "get_mintcoin",
    "get_contract_binary",
    "get_contract_history_iter",
    "get_contract_storage",
    "get_utxo_iter",
    "get_unspents_iter"
]
