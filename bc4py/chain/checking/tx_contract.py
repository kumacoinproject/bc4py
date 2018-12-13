from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.checking.signature import *
from bc4py.database.builder import tx_builder
from bc4py.database.validator import *
from bc4py.database.contract import *
from nem_ed25519.key import is_address
from binascii import hexlify
import bjson


def check_tx_contract_conclude(tx: TX, include_block: Block):
    # common check
    if not (len(tx.inputs) > 0 and len(tx.inputs) > 0):
        raise BlockChainError('No inputs or outputs.')
    elif tx.message_type != C.MSG_BYTE:
        raise BlockChainError('validator_edit_tx is bytes msg.')
    elif V.BLOCK_CONTRACT_PREFIX is None:
        raise BlockChainError('Not set contract prefix ?')
    elif V.BLOCK_CONTRACT_PREFIX == V.BLOCK_PREFIX:
        raise BlockChainError('normal prefix same with contract prefix.')
    try:
        c_address, start_hash, c_storage = bjson.loads(tx.message)
    except Exception as e:
        raise BlockChainError('BjsonError: {}'.format(e))
    if not (isinstance(c_address, str) and len(c_address) == 40):
        raise BlockChainError('1. Not correct format. {}'.format(c_address))
    if not (isinstance(start_hash, bytes) and len(start_hash) == 32):
        raise BlockChainError('2. Not correct format. {}'.format(start_hash))
    if not (c_storage is None or isinstance(c_storage, dict)):
        raise BlockChainError('3. Not correct format. {}'.format(c_storage))
    # check already created conclude tx
    for finish_hash in get_conclude_by_start_iter(c_address=c_address, start_hash=start_hash,
                                                  best_block=include_block, stop_txhash=tx.hash):
        if finish_hash and finish_hash != tx.hash:
            raise BlockChainError('Already start_hash used. {}'.format(hexlify(finish_hash).decode()))
    # inputs address check
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            raise BlockChainError('Not found input tx.')
        address, coin_id, amount = input_tx.outputs[txindex]
        if address != c_address:
            raise BlockChainError('Not contract address. {}'.format(address))
    # validator check
    v = get_validator_object(c_address=c_address, best_block=include_block, stop_txhash=tx.hash)
    if v.require == 0:
        raise BlockChainError('At least 1 validator required. {}'.format(v.require))
    # check start tx
    start_tx = tx_builder.get_tx(txhash=start_hash)
    if start_tx is None:
        raise BlockChainError('Not found start tx. {}'.format(hexlify(start_hash).decode()))
    if start_tx.height is None:
        raise BlockChainError('Start tx is unconfirmed. {}'.format(start_tx))
    if start_tx.type != C.TX_TRANSFER:
        raise BlockChainError('Start tx is TRANSFER, not {}.'.format(C.txtype2name.get(start_tx.type, None)))
    if start_tx.message_type != C.MSG_BYTE:
        raise BlockChainError('Start tx is MSG_BYTE, not {}.'.format(C.msg_type2name.get(start_tx.message_type, None)))
    if start_tx.time != tx.time or start_tx.deadline != tx.deadline:
        raise BlockChainError('time of conclude_tx and start_tx is same, {}!={}.'.format(start_tx.time, tx.time))
    try:
        c_start_address, c_method, redeem_address, c_args = bjson.loads(start_tx.message)
    except Exception as e:
        raise BlockChainError('BjsonError: {}'.format(e))
    if c_address != c_start_address:
        raise BlockChainError('Start tx\'s contract address is different. {}!={}'.format(c_address, c_start_address))
    if not isinstance(c_method, str):
        raise BlockChainError('c_method is string. {}'.format(c_method))
    if not (isinstance(c_args, tuple) or isinstance(c_args, list)):
        raise BlockChainError('4. Not correct format. {}'.format(c_args))
    # contract check
    c_before = get_contract_object(c_address=c_address, best_block=include_block, stop_txhash=tx.hash)
    if c_method == M_INIT:
        if len(c_args) != 3:
            raise BlockChainError('c_args is 3 items.')
        if c_before.index != -1:
            raise BlockChainError('Already created contract. {}'.format(c_before.index))
        c_bin, c_extra_imports, c_settings = c_args
        if not isinstance(c_bin, bytes):
            raise BlockChainError('5. Not correct format. {}'.format(c_args))
        if not (c_extra_imports is None or isinstance(c_extra_imports, tuple) or isinstance(c_extra_imports, list)):
            raise BlockChainError('6. Not correct format. {}'.format(c_extra_imports))
        if not (c_settings is None or isinstance(c_settings, dict)):
            raise BlockChainError('7. Not correct format. {}'.format(c_settings))
    elif c_method == M_UPDATE:
        if len(c_args) != 3:
            raise BlockChainError('c_args is 3 items.')
        if c_before.index == -1:
            raise BlockChainError('Not created contract.')
        c_bin, c_extra_imports, c_settings = c_args
        if not (c_bin is None or isinstance(c_bin, bytes)):
            raise BlockChainError('8. Not correct format. {}'.format(c_args))
        if not (c_extra_imports is None or isinstance(c_extra_imports, tuple)):
            raise BlockChainError('9. Not correct format. {}'.format(c_extra_imports))
        if not (c_settings is None or isinstance(c_settings, dict)):
            raise BlockChainError('10. Not correct format. {}'.format(c_settings))
        if not (c_bin or c_extra_imports or c_settings):
            raise BlockChainError('No change found. {}, {}, {}'.format(c_bin, c_extra_imports, c_settings))
    else:
        pass  # user oriented data
    contract_required_gas_check(tx=tx, v=v, extra_gas=0)
    contract_signature_check(extra_tx=tx, v=v, include_block=include_block)


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
    # message
    try:
        c_address, new_address, flag, sig_diff = bjson.loads(tx.message)
    except Exception as e:
        raise BlockChainError('BjsonError: {}'.format(e))
    # inputs/outputs address check
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            raise BlockChainError('Not found input tx.')
        address, coin_id, amount = input_tx.outputs[txindex]
        if address != c_address:
            raise BlockChainError('1 Not contract address. {}'.format(address))
    for address, coin_id, amount in tx.outputs:
        if address != c_address:
            raise BlockChainError('2 Not contract address. {}'.format(address))
    # check new_address
    v_before = get_validator_object(c_address=c_address, best_block=include_block, stop_txhash=tx.hash)
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
    contract_required_gas_check(tx=tx, v=v_before, extra_gas=C.VALIDATOR_EDIT_GAS)
    contract_signature_check(extra_tx=tx, v=v_before, include_block=include_block)


def contract_signature_check(extra_tx: TX, v: Validator, include_block: Block):
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


def contract_required_gas_check(tx: TX, v: Validator, extra_gas=0):
    # gas/cosigner fee check
    require_gas = tx.size + C.SIGNATURE_GAS*v.require + extra_gas
    if tx.gas_amount < require_gas:
        raise BlockChainError('Unsatisfied required gas. [{}<{}]'.format(tx.gas_amount, require_gas))


__all__ = [
    "check_tx_contract_conclude",
    "check_tx_validator_edit",
]
