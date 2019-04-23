from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.checking.signature import *
from bc4py.database.builder import tx_builder
from bc4py.database.validator import *
from bc4py.database.contract import *
from nem_ed25519 import is_address
from logging import getLogger

log = getLogger('bc4py')


def check_tx_contract_conclude(tx: TX, include_block: Block):
    # common check
    if not (len(tx.inputs) > 0 and len(tx.inputs) > 0):
        raise BlockChainError('No inputs or outputs.')
    elif tx.message_type != C.MSG_MSGPACK:
        raise BlockChainError('validator_edit_tx is MSG_MSGPACK.')
    elif V.BLOCK_CONTRACT_PREFIX is None:
        raise BlockChainError('Not set contract prefix ?')
    elif V.BLOCK_CONTRACT_PREFIX == V.BLOCK_PREFIX:
        raise BlockChainError('normal prefix same with contract prefix.')
    try:
        c_address, start_hash, c_storage = tx.encoded_message()
    except Exception as e:
        raise BlockChainError('EncodeMessageError: {}'.format(e))
    if not (isinstance(c_address, str) and len(c_address) == 40):
        raise BlockChainError('1. Not correct format. {}'.format(c_address))
    if not (isinstance(start_hash, bytes) and len(start_hash) == 32):
        raise BlockChainError('2. Not correct format. {}'.format(start_hash))
    if not (c_storage is None or isinstance(c_storage, dict)):
        raise BlockChainError('3. Not correct format. {}'.format(c_storage))
    # check already created conclude tx
    finish_hash = get_conclude_hash_from_start(
        c_address=c_address, start_hash=start_hash, best_block=include_block)
    if finish_hash and finish_hash != tx.hash:
        raise BlockChainError('Already start_hash used. {}'.format(finish_hash.hex()))
    # check start tx
    start_tx = tx_builder.get_tx(txhash=start_hash)
    if start_tx is None:
        raise BlockChainError('Not found start tx. {}'.format(start_hash.hex()))
    if start_tx.height is None:
        raise BlockChainError('Start tx is unconfirmed. {}'.format(start_tx))
    if start_tx.type != C.TX_TRANSFER:
        raise BlockChainError('Start tx is TRANSFER, not {}.'.format(C.txtype2name.get(start_tx.type, None)))
    if start_tx.message_type != C.MSG_MSGPACK:
        raise BlockChainError('Start tx is MSG_MSGPACK, not {}.'.format(
            C.msg_type2name.get(start_tx.message_type, None)))
    if start_tx.time != tx.time or start_tx.deadline != tx.deadline:
        raise BlockChainError('time of conclude_tx and start_tx is same, {}!={}.'.format(start_tx.time, tx.time))
    try:
        c_start_address, c_method, redeem_address, c_args = start_tx.encoded_message()
    except Exception as e:
        raise BlockChainError('BjsonError: {}'.format(e))
    if c_address != c_start_address:
        raise BlockChainError('Start tx\'s contract address is different. {}!={}'.format(
            c_address, c_start_address))
    if not isinstance(c_method, str):
        raise BlockChainError('c_method is string. {}'.format(c_method))
    if not (isinstance(c_args, tuple) or isinstance(c_args, list)):
        raise BlockChainError('4. Not correct format. {}'.format(c_args))
    # contract check
    c_before = get_contract_object(c_address=c_address, best_block=include_block, stop_txhash=tx.hash)
    # contract index check
    if c_before.version != -1:
        new_index = start_tx2index(start_tx=start_tx)
        if not (c_before.db_index < new_index):
            raise BlockChainError('The index is old on execute order, '
                                  'before={} new={}'.format(c_before.db_index, new_index))
        # check:  Do not skip old contract?
        if include_block:
            c_my_before = get_contract_object(c_address=c_address, best_block=None, stop_txhash=tx.hash)
            if c_my_before.version != c_before.version or c_my_before.db_index != c_before.db_index:
                raise BlockChainError('Block skip old ConcludeTX, idx={} my={} block={}'.format(
                    new_index, c_my_before, c_before))
    else:
        pass  # init ConcludeTX, no action
    # c_method check, init, update and others..
    if c_method == M_INIT:
        if len(c_args) != 4:
            raise BlockChainError('c_args is 4 items.')
        if c_before.version != -1:
            raise BlockChainError('Already created contract. {}'.format(c_before.version))
        c_bin, v_address, c_extra_imports, c_settings = c_args
        if not isinstance(c_bin, bytes):
            raise BlockChainError('5. Not correct format. {}'.format(c_args))
        if not (isinstance(v_address, str) and len(v_address) == 40):
            raise BlockChainError('1 ValidatorAddress format is not correct {}'.format(v_address))
        if not is_address(v_address, V.BLOCK_VALIDATOR_PREFIX):
            raise BlockChainError('2 ValidatorAddress format is not correct {}'.format(v_address))
        if not (c_extra_imports is None or isinstance(c_extra_imports, tuple) or
                isinstance(c_extra_imports, list)):
            raise BlockChainError('6. Not correct format. {}'.format(c_extra_imports))
        if not (c_settings is None or isinstance(c_settings, dict)):
            raise BlockChainError('7. Not correct format. {}'.format(c_settings))
    elif c_method == M_UPDATE:
        if len(c_args) != 3:
            raise BlockChainError('c_args is 3 items.')
        if c_before.version == -1:
            raise BlockChainError('Not created contract.')
        c_bin, c_extra_imports, c_settings = c_args
        v_address = c_before.v_address
        if not (c_bin is None or isinstance(c_bin, bytes)):
            raise BlockChainError('8. Not correct format. {}'.format(c_args))
        if not (c_extra_imports is None or isinstance(c_extra_imports, tuple)):
            raise BlockChainError('9. Not correct format. {}'.format(c_extra_imports))
        if not (c_settings is None or isinstance(c_settings, dict)):
            raise BlockChainError('10. Not correct format. {}'.format(c_settings))
        if not (c_bin or c_extra_imports or c_settings):
            raise BlockChainError('No change found. {}, {}, {}'.format(c_bin, c_extra_imports, c_settings))
    else:
        v_address = c_before.v_address  # user oriented data
    # validator check
    v = get_validator_object(v_address=v_address, best_block=include_block, stop_txhash=tx.hash)
    if v.require == 0:
        raise BlockChainError('At least 1 validator required. {}'.format(v.require))
    required_gas_check(tx=tx, v=v, extra_gas=0)
    objective_tx_signature_check(target_address=c_address, extra_tx=tx, v=v, include_block=include_block)


def check_tx_validator_edit(tx: TX, include_block: Block):
    # common check
    if not (len(tx.inputs) > 0 and len(tx.inputs) > 0):
        raise BlockChainError('No inputs or outputs.')
    elif tx.message_type != C.MSG_MSGPACK:
        raise BlockChainError('validator_edit_tx is MSG_MSGPACK.')
    elif V.BLOCK_CONTRACT_PREFIX is None:
        raise BlockChainError('Not set contract prefix ?')
    elif V.BLOCK_CONTRACT_PREFIX == V.BLOCK_PREFIX:
        raise BlockChainError('normal prefix same with contract prefix.')
    # message
    try:
        v_address, new_address, flag, sig_diff = tx.encoded_message()
    except Exception as e:
        raise BlockChainError('BjsonError: {}'.format(e))
    # check new_address
    v_before = get_validator_object(v_address=v_address, best_block=include_block, stop_txhash=tx.hash)
    if new_address:
        if not is_address(ck=new_address, prefix=V.BLOCK_PREFIX):
            raise BlockChainError('new_address is normal prefix.')
        elif flag == F_NOP:
            raise BlockChainError('input new_address, but NOP.')
    if v_before.version == -1:
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
            raise BlockChainError('sig_diff check failed, 0 < {} <= {}.'.format(next_require_num,
                                                                                next_validator_num))
    required_gas_check(tx=tx, v=v_before, extra_gas=C.VALIDATOR_EDIT_GAS)
    objective_tx_signature_check(target_address=v_address, extra_tx=tx, v=v_before, include_block=include_block)


def objective_tx_signature_check(target_address, extra_tx: TX, v: Validator, include_block: Block):
    necessary_cks = set(v.validators)
    necessary_num = v.require
    checked_cks = set()
    for txhash, txindex in extra_tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            raise BlockChainError('1 Not found input {}:{}'.format(txhash.hex(), txindex))
        if len(input_tx.outputs) < txindex:
            raise BlockChainError('2 Not found input {}:{}'.format(txhash.hex(), txindex))
        address, coin_id, amount = input_tx.outputs[txindex]
        if address in checked_cks:
            continue
        elif address == target_address:
            continue
        elif is_address(address, V.BLOCK_PREFIX):
            if address not in necessary_cks:
                necessary_num += 1
                necessary_cks.add(address)
        elif is_address(address, V.BLOCK_VALIDATOR_PREFIX):
            raise BlockChainError('Not allowed {}'.format(address))
        elif is_address(address, V.BLOCK_CONTRACT_PREFIX):
            raise BlockChainError('Not allowed {}'.format(address))
        else:
            raise BlockChainError('Not found address prefix {}'.format(address))
        checked_cks.add(address)

    signed_cks = get_signed_cks(extra_tx)
    accept_cks = signed_cks & necessary_cks
    reject_cks = signed_cks - necessary_cks
    if len(reject_cks) > 0:
        raise BlockChainError('Unrelated signature include, reject={}'.format(reject_cks))
    elif include_block:
        # check satisfy require?
        if len(accept_cks) < necessary_num:
            raise BlockChainError('Not satisfied require signature. [signed={}, accepted={}, require={}]'.format(
                signed_cks, accept_cks, necessary_num))
    else:
        # check can marge?
        original_tx = tx_builder.get_tx(txhash=extra_tx.hash)
        if original_tx is None:
            # accept the tx first
            if 0 < necessary_num and len(accept_cks) == 0:
                raise BlockChainError('No acceptable signature. signed={}'.format(signed_cks))
            if len(accept_cks) > necessary_num:
                # accept signature more than required
                log.debug('Too many signatures, accept={} req={}'.format(accept_cks, necessary_num))
        else:
            # need to marge signature
            if original_tx.height is not None:
                raise BlockChainError('Already included tx. height={}'.format(original_tx.height))
            if necessary_num == 0:
                raise BlockChainError('Don\t need to marge signature.')
            original_cks = get_signed_cks(original_tx)
            accept_new_cks = (signed_cks - original_cks) & necessary_cks
            if len(accept_new_cks) == 0:
                raise BlockChainError('No new acceptable cks. ({} - {}) & {}'.format(
                    signed_cks, original_cks, necessary_cks))
            if len(accept_new_cks) + len(original_cks) > necessary_num:
                # accept signature more than required
                log.debug('Too many signatures, new={} original={} req={}'.format(
                    accept_new_cks, original_cks, necessary_num))


def required_gas_check(tx: TX, v: Validator, extra_gas=0):
    # gas/cosigner fee check
    require_gas = tx.size + C.SIGNATURE_GAS * v.require + extra_gas
    if tx.gas_amount < require_gas:
        raise BlockChainError('Unsatisfied required gas. [{}<{}]'.format(tx.gas_amount, require_gas))


__all__ = [
    "check_tx_contract_conclude",
    "check_tx_validator_edit",
]
