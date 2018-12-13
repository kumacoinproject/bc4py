from bc4py.config import C, V, BlockChainError
from bc4py.chain import TX
from bc4py.database import contract
from bc4py.database.validator import F_NOP, F_REMOVE, F_ADD, get_validator_object
from bc4py.database.builder import tx_builder
from bc4py.database.account import create_new_user_keypair, read_user2name
from bc4py.user.txcreation.utils import *
from bc4py.user.txcreation.transfer import send_many
import bjson
from copy import deepcopy
import logging


def create_contract_init_tx(c_address, c_bin, cur, c_extra_imports=None, c_settings=None,
                            send_pairs=None, sender=C.ANT_UNKNOWN, gas_price=None, retention=10800):
    if sender in (C.ANT_OUTSIDE, C.ANT_RESERVED):
        raise BlockChainError('Not allowed inner account.')
    c_method = contract.M_INIT
    c_args = (c_bin, c_extra_imports, c_settings)
    redeem_address = create_new_user_keypair(read_user2name(sender, cur), cur)
    msg_body = bjson.dumps((c_address, c_method, redeem_address, c_args), compress=False)
    send_pairs = send_pairs_format_check(c_address=c_address, send_pairs=send_pairs)
    tx = send_many(sender=sender, send_pairs=send_pairs, cur=cur, fee_coin_id=0, gas_price=gas_price,
                   msg_type=C.MSG_BYTE, msg_body=msg_body, retention=retention)
    return tx


def create_contract_update_tx(c_address, cur, c_bin=None, c_extra_imports=None, c_settings=None,
                              send_pairs=None, sender=C.ANT_UNKNOWN, gas_price=None, retention=10800):
    assert c_bin or c_extra_imports or c_settings
    if sender in (C.ANT_OUTSIDE, C.ANT_RESERVED):
        raise BlockChainError('Not allowed inner account.')
    c_method = contract.M_UPDATE
    c_args = (c_bin, c_extra_imports, c_settings)
    redeem_address = create_new_user_keypair(read_user2name(sender, cur), cur)
    msg_body = bjson.dumps((c_address, c_method, redeem_address, c_args), compress=False)
    send_pairs = send_pairs_format_check(c_address=c_address, send_pairs=send_pairs)
    tx = send_many(sender=sender, send_pairs=send_pairs, cur=cur, fee_coin_id=0, gas_price=gas_price,
                   msg_type=C.MSG_BYTE, msg_body=msg_body, retention=retention)
    return tx


def create_contract_transfer_tx(c_address, cur, c_method, c_args=None,
                                send_pairs=None, sender=C.ANT_UNKNOWN, gas_price=None, retention=10800):
    assert isinstance(c_method, str)
    if sender in (C.ANT_OUTSIDE, C.ANT_RESERVED):
        raise BlockChainError('Not allowed inner account.')
    if c_args is None:
        c_args = tuple()
    else:
        c_args = tuple(c_args)
    redeem_address = create_new_user_keypair(read_user2name(sender, cur), cur)
    msg_body = bjson.dumps((c_address, c_method, redeem_address, c_args), compress=False)
    send_pairs = send_pairs_format_check(c_address=c_address, send_pairs=send_pairs)
    tx = send_many(sender=sender, send_pairs=send_pairs, cur=cur, fee_coin_id=0, gas_price=gas_price,
                   msg_type=C.MSG_BYTE, msg_body=msg_body, retention=retention)
    return tx


def create_conclude_tx(c_address, start_tx, redeem_address, send_pairs=None, c_storage=None, emulate_gas=0):
    assert isinstance(start_tx, TX)
    assert send_pairs is None or isinstance(send_pairs, list)
    assert c_storage is None or isinstance(c_storage, dict)
    assert isinstance(emulate_gas, int)
    message = bjson.dumps((c_address, start_tx.hash, c_storage), compress=False)
    v = get_validator_object(c_address=c_address)
    send_pairs = send_pairs or list()
    tx = TX(tx={
        'type': C.TX_CONCLUDE_CONTRACT,
        'time': start_tx.time,
        'deadline': start_tx.deadline,
        'gas_price': start_tx.gas_price,
        'gas_amount': 0,
        'outputs': [tuple(s) for s in send_pairs],
        'message_type': C.MSG_BYTE,
        'message': message})
    extra_gas = C.SIGNATURE_GAS * v.require
    tx.gas_amount = tx.size + extra_gas
    # fill unspents
    fill_contract_inputs_outputs(tx=tx, c_address=c_address, additional_gas=extra_gas)
    # replace dummy address
    replace_redeem_dummy_address(tx=tx, replace_by=c_address)
    # fix redeem fees
    if send_pairs:
        # conclude_txで使用したGasを、ユーザーから引いてコントラクトに戻す処理
        conclude_fee = (emulate_gas + tx.gas_amount) * tx.gas_price
        fee_coin_id = 0
        f_finish_add = f_finish_sub = False
        for index, (address, coin_id, amount) in enumerate(tx.outputs):
            if coin_id != fee_coin_id:
                continue
            elif not f_finish_add and address == c_address:
                f_finish_add = True
                tx.outputs[index] = (address, coin_id, amount + conclude_fee)
            elif not f_finish_sub and address == redeem_address:
                f_finish_sub = True
                tx.outputs[index] = (address, coin_id, amount - conclude_fee)
            else:
                pass
        if not (f_finish_add and f_finish_sub):
            raise BlockChainError('Cannot move conclude fee, add={} sub={}'
                                  .format(f_finish_add, f_finish_sub))
        logging.debug("Move conclude fee {}:{}".format(fee_coin_id, conclude_fee))
    tx.serialize()
    if v.index == -1:
        raise BlockChainError('Not init validator address. {}'.format(c_address))
    if setup_contract_signature(tx, v.validators) == 0:
        raise BlockChainError('Cannot sign, you are not validator.')
    return tx


def create_validator_edit_tx(c_address, new_address=None,
                             flag=F_NOP, sig_diff=0, gas_price=None, retention=10800):
    assert not (flag == F_NOP and sig_diff == 0), 'No edit info.'
    if new_address is None and flag != F_NOP:
        raise BlockChainError('No cosigner edit, but flag is not NOP.')
    # validator object
    v = get_validator_object(c_address=c_address)
    if v.index == -1:
        if new_address is None or flag != F_ADD or sig_diff != 1:
            raise BlockChainError('Not correct info.')
    else:
        next_require = v.require + sig_diff
        next_validator_num = len(v.validators)
        if flag == F_ADD:
            next_validator_num += 1
        elif flag == F_REMOVE:
            next_validator_num -= 1
        if not (0 < next_require <= next_validator_num):
            raise BlockChainError('ReqError, 0 < {} <= {}'.format(next_require, next_validator_num))
    # tx create
    message = bjson.dumps((c_address, new_address, flag, sig_diff), compress=False)
    tx = TX(tx={
        'type': C.TX_VALIDATOR_EDIT,
        'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
        'gas_amount': 0,
        'message_type': C.MSG_BYTE,
        'message': message})
    extra_gas = C.VALIDATOR_EDIT_GAS + C.SIGNATURE_GAS * v.require
    tx.gas_amount = tx.size + extra_gas
    tx.update_time(retention)
    # fill unspents
    fill_contract_inputs_outputs(tx=tx, c_address=c_address, additional_gas=extra_gas)
    # replace dummy address
    replace_redeem_dummy_address(tx=tx, replace_by=c_address)
    tx.serialize()
    if len(v.validators) > 0 and setup_contract_signature(tx, v.validators) == 0:
        raise BlockChainError('Cannot sign, you are not validator.')
    return tx


def create_signed_tx_as_validator(tx: TX):
    assert tx.type in (C.TX_VALIDATOR_EDIT, C.TX_CONCLUDE_CONTRACT)
    assert tx.hash in tx_builder.unconfirmed
    copied_tx = deepcopy(tx)
    # sign as another validator
    c_address, *dummy = bjson.loads(copied_tx.message)
    # validator object
    stop_txhash = copied_tx.hash if copied_tx.type == C.TX_VALIDATOR_EDIT else None
    v = get_validator_object(c_address=c_address, stop_txhash=stop_txhash)
    if setup_contract_signature(copied_tx, v.validators) == 0:
        raise BlockChainError('Cannot sign, you are not validator or already signed.')
    return copied_tx


def send_pairs_format_check(c_address, send_pairs):
    # send_pairs is list and inner pair is tuple.
    if send_pairs is None:
        send_pairs = [(c_address, 0, C.CONTRACT_MINIMUM_INPUT)]
    elif isinstance(send_pairs, list):
        send_pairs = [tuple(s) for s in send_pairs]
    else:
        raise BlockChainError('Not correct format. {}'.format(send_pairs))
    return send_pairs


__all__ = [
    "create_contract_transfer_tx",
    "create_contract_init_tx",
    "create_contract_update_tx",
    "F_NOP", "F_REMOVE", "F_ADD",
    "create_conclude_tx",
    "create_validator_edit_tx",
    "create_signed_tx_as_validator",
]
