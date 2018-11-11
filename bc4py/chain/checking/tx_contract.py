from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.contract.tools import binary2contract
from bc4py.chain.checking.signature import *
from bc4py.database.builder import tx_builder
from bc4py.database.validator import *
from nem_ed25519.key import is_address, convert_address
import bjson
import logging
import threading


def check_tx_contract_conclude(tx: TX, include_block: Block):
    pass


def check_tx_validator_edit(tx: TX, include_block: Block):
    # common check
    if not (len(tx.inputs) > 0 and len(tx.inputs) > 0):
        raise BlockChainError('No inputs or outputs.')
    elif tx.message_type != C.MSG_BYTE:
        raise BlockChainError('validator_edit_tx is bytes msg.')
    elif V.BLOCK_CONTRACT_PREFIX is None:
        raise BlockChainError('Not set contract prefix ?')
    elif V.BLOCK_CONTRACT_PREFIX == V.BLOCK_PREFIX:
        raise BlockChainError('normal prefix same with contract prefix.')
    # inputs/outputs address check
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            raise BlockChainError('Not found input tx.')
        address, coin_id, amount = input_tx.outputs[txindex]
        if not is_address(ck=address, prefix=V.BLOCK_CONTRACT_PREFIX):
            raise BlockChainError('Not contract address. {}'.format(address))
    for address, coin_id, amount in tx.outputs:
        if not is_address(ck=address, prefix=V.BLOCK_CONTRACT_PREFIX):
            raise BlockChainError('Not contract address. {}'.format(address))
    # message check
    c_address, new_address, flag, sig_diff = bjson.loads(tx.message)
    v_before = get_validator_object(c_address=c_address, best_block=include_block, stop_txhash=tx.hash)
    # check new_address
    if new_address:
        if not is_address(ck=new_address, prefix=V.BLOCK_PREFIX):
            raise BlockChainError('new_address is normal prefix.')
        elif flag == F_NOP:
            raise BlockChainError('input new_address, but NOP.')
    if v_before.index == -1:
        # create validator for the first time
        if new_address is None:
            raise BlockChainError('Not setup new_address.')
        elif flag != F_ADD:
            raise BlockChainError('Need to add new_address flag.')
        elif sig_diff != 1:
            raise BlockChainError('sig_diff is 1.')
    else:
        # edit already created validator
        next_validator_num = len(v_before.validators)  # Note: Add/Remove after
        next_require_num = v_before.require + sig_diff
        if flag == F_ADD:
            if new_address is None:
                raise BlockChainError('Not setup new_address.')
            elif new_address in v_before.validators:
                raise BlockChainError('Already included new_address.')
            next_validator_num += 1
        elif flag == F_REMOVE:
            if new_address is None:
                raise BlockChainError('Not setup new_address.')
            elif new_address not in v_before.validators:
                raise BlockChainError('Not include new_address.')
            elif len(v_before.validators) < 2:
                raise BlockChainError('validator is now only {}.'.format(len(v_before.validators)))
            next_validator_num -= 1
        elif flag == F_NOP:
            if new_address is not None:
                raise BlockChainError('Input new_address?')
        else:
            raise BlockChainError('unknown flag {}.'.format(flag))
        # sig_diff check
        if not (0 < next_require_num <= next_validator_num):
            raise BlockChainError('sig_diff check failed, 0 < {} <= {}.'
                                  .format(next_require_num, next_validator_num))
    # gas/cosigner fee check
    require_gas = len(tx.b) + C.VALIDATOR_EDIT_GAS + (C.SIGNATURE_GAS + 96) * v_before.require
    if tx.gas_amount < require_gas:
        raise BlockChainError('Unsatisfied required gas. [{}<{}]'.format(tx.gas_amount, require_gas))
    contract_signature_check(extra_tx=tx, v=v_before, include_block=include_block)


def contract_signature_check(extra_tx: TX, v: Validator, include_block: Block):
    batch_sign_cashe([extra_tx])
    signed_cks = get_signed_cks(extra_tx)
    accept_cks = signed_cks & set(v.validators)
    if include_block:
        # check satisfy require?
        if len(accept_cks) < v.require:
            raise BlockChainError('Not satisfied require signature. [signed={}, accepted={}, require={}]'
                                  .format(signed_cks, accept_cks, v.require))
    else:
        # check can marge?
        original_tx = tx_builder.get_tx(txhash=extra_tx.hash)
        if original_tx is None:
            # not accept before
            if 0 < v.require and len(accept_cks) == 0:
                raise BlockChainError('No acceptable signature. signed={}'.format(signed_cks))
        else:
            # need to marge signature
            if original_tx.height is not None:
                raise BlockChainError('Already included tx. height={}'.format(original_tx.height))
            if v.require == 0:
                raise BlockChainError('Don\t need to marge signature.')
            original_cks = get_signed_cks(original_tx)
            accept_new_cks = (signed_cks - original_cks) & set(v.validators)
            if len(accept_new_cks) == 0:
                raise BlockChainError('No new acceptable cks. ({} - {}) & {}'
                                      .format(signed_cks, original_cks, set(v.validators)))


"""def check_tx_create_contract(tx: TX, include_block: Block):
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
        raise BlockChainError('Already created contract. {}'.format(tx))"""


"""def check_tx_start_contract(start_tx: TX, include_block: Block):
    # 共通チェック
    c_address, c_data, c_args, c_redeem = bjson.loads(start_tx.message)
    if not is_address(c_address, V.BLOCK_CONTRACT_PREFIX):
        raise BlockChainError('Is not contract address. {}'.format(c_address))
    elif not (c_args is None or isinstance(c_args, list) or isinstance(c_args, tuple)):
        raise BlockChainError('c_args is {}'.format(type(c_args)))
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
        c_address, c_method, c_args, c_redeem = bjson.loads(start_tx.message)
        get_contract_binary(c_address)
        if P.VALIDATOR_OBJ and im_a_validator(include_block):
            P.VALIDATOR_OBJ.put_unvalidated(start_tx)
            logging.debug("Add validation que {}".format(start_tx))"""


"""def get_start_by_finish_tx(finish_tx, start_hash, include_block):
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
            raise BlockChainError('Not found StartTX on Unconfirmed. {}'.format(finish_tx))"""


"""def check_tx_finish_contract(finish_tx, include_block):
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
                                  .format(include_block.txs.index(start_tx), include_block.txs.index(finish_tx)))"""


__all__ = [
    "check_tx_contract_conclude",
    "check_tx_validator_edit",
]
