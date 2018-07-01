from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.user.utils import im_a_validator
from bc4py.database.tools import get_contract_storage
from bc4py.contract.tools import binary2contract
from bc4py.database.builder import tx_builder
from nem_ed25519.key import is_address
import bjson
import logging
import threading


def check_tx_create_contract(tx: TX, include_block: Block):
    if len(tx.inputs) == 0 or len(tx.outputs) == 0:
        raise BlockChainError('No inputs or outputs.')
    elif tx.message_type != C.MSG_BYTE:
        raise BlockChainError('create contract tx is bytes msg.')
    elif V.BLOCK_CONTRACT_PREFIX is None:
        raise BlockChainError('Not set contract prefix ?')
    elif V.BLOCK_CONTRACT_PREFIX == V.BLOCK_PREFIX:
        raise BlockChainError('normal prefix same with contract prefix.')
    # GAS量チェック
    estimate_gas = tx.getsize() + C.CONTRACT_CREATE_FEE
    if estimate_gas > tx.gas_amount:
        raise BlockChainError('Insufficient gas [{}>{}]'.format(estimate_gas, tx.gas_amount))
    # Contractをデコードできるか
    c_address, c_bin, c_cs = bjson.loads(tx.message)
    binary2contract(c_bin)
    # ContractStorageの初期値チェック
    if c_cs:
        for k, v in c_cs.items():
            if not isinstance(k, bytes) or not isinstance(v, bytes):
                raise BlockChainError('cs format is wrong. {}'.format(c_cs))
    if not is_address(c_address, V.BLOCK_CONTRACT_PREFIX):
        raise BlockChainError('Is not contract address. {}'.format(c_address))
    # 既に登録されていないかチェック
    cs = get_contract_storage(c_address, include_block)
    if cs.version != 0:
        raise BlockChainError('Already created contract. {}'.format(tx))


def check_tx_start_contract(start_tx: TX, include_block: Block):
    # 共通チェック
    c_address, c_data, c_args, c_redeem = bjson.loads(start_tx.message)
    if not is_address(c_address, V.BLOCK_CONTRACT_PREFIX):
        raise BlockChainError('Is not contract address. {}'.format(c_address))
    elif not is_address(c_redeem, V.BLOCK_PREFIX):
        raise BlockChainError('Is not redeem address. {}'.format(c_redeem))
    elif start_tx.gas_price < V.COIN_MINIMUM_PRICE:
        raise BlockChainError('GasPrice is too low. [{}<{}]'.format(start_tx.gas_price, V.COIN_MINIMUM_PRICE))
    elif start_tx.gas_amount < V.CONTRACT_MINIMUM_AMOUNT:
        raise BlockChainError('GasAmount is too low. [{}<{}]'.format(start_tx.gas_amount, V.CONTRACT_MINIMUM_AMOUNT))

    # Block内チェック
    if include_block:
        # 同一のStartTXを示すFinishTXが存在しないかチェック
        count = 0
        for finish_tx in include_block.txs:
            if finish_tx.type != C.TX_FINISH_CONTRACT:
                continue
            c_status, c_start_hash, c_diff = bjson.loads(finish_tx.message)
            if c_start_hash != start_tx.hash:
                continue
            count += 1
        if count == 0:
            raise BlockChainError('Not found FinishTX on block. {}'.format(start_tx))
        if count > 1:
            raise BlockChainError('Find some FinishTX on block. {}'.format(count))

    else:
        # TODO: Validatorとしてチェックし、FinishTXを発行
        if P.F_VALIDATOR and im_a_validator(include_block):
            def check():
                pass
            threading.Thread(target=check, name='Validate').start()


def get_start_by_finish_tx(finish_tx, start_hash, include_block):
    if include_block:
        for start_tx in include_block.txs:
            if start_tx.type != C.TX_START_CONTRACT:
                pass
            elif start_tx.hash == start_hash:
                return start_tx
        else:
            raise BlockChainError('Not found StartTX on block. {} {}'.format(finish_tx, include_block))
    else:
        if start_hash in tx_builder.unconfirmed:
            start_tx = tx_builder.unconfirmed[start_hash]
            if start_tx.type != C.TX_START_CONTRACT:
                pass
            elif start_tx.hash == start_hash:
                return start_tx
        else:
            raise BlockChainError('Not found StartTX on Unconfirmed. {}'.format(finish_tx))


def check_tx_finish_contract(finish_tx, include_block):
    if finish_tx.message_type != C.MSG_BYTE:
        raise BlockChainError('message type is bytes.')
    finish_status, start_hash, finish_diff = bjson.loads(finish_tx.message)
    # StartTXを探し出す
    start_tx = get_start_by_finish_tx(finish_tx, start_hash, include_block)
    # FinishTXとStartTXの整合性チェック
    if start_tx.gas_price != finish_tx.gas_price:
        raise BlockChainError('StartGasPrice differ from FinishGasPrice. [{}!={}]'
                              .format(start_tx.gas_price,finish_tx.gas_price))
    elif finish_tx.gas_amount > 0:
        raise BlockChainError('Not redeem amount found. [{}>0]'.format(finish_tx.gas_amount))
    elif include_block:
        if include_block.txs.index(start_tx) >= include_block.txs.index(finish_tx):
            raise BlockChainError('start tx index is higher than finish tx. [{}>={}]'
                                  .format(include_block.txs.index(start_tx), include_block.txs.index(finish_tx)))


__all__ = [
    "check_tx_create_contract",
    "check_tx_start_contract",
    "check_tx_finish_contract"
]
