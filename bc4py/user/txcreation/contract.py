from bc4py.config import C, V, BlockChainError
from bc4py.chain.tx import TX
from bc4py.database import contract
from bc4py.database.validator import F_NOP, F_REMOVE, F_ADD, get_validator_object
from bc4py.database.contract import get_validator_by_contract_info
from bc4py.database.account import create_new_user_keypair
from bc4py.user.txcreation.utils import *
from bc4py.user.txcreation.transfer import send_many
from copy import deepcopy
from logging import getLogger
import msgpack

log = getLogger('bc4py')


def create_contract_init_tx(c_address,
                            v_address,
                            c_bin,
                            cur,
                            c_extra_imports=None,
                            c_settings=None,
                            send_pairs=None,
                            sender=C.ANT_UNKNOWN,
                            gas_price=None,
                            retention=10800):
    c_method = contract.M_INIT
    c_args = (c_bin, v_address, c_extra_imports, c_settings)
    redeem_address = create_new_user_keypair(sender, cur, True)
    msg_body = msgpack.packb((c_address, c_method, redeem_address, c_args), use_bin_type=True)
    send_pairs = send_pairs_format_check(c_address=c_address, send_pairs=send_pairs)
    tx = send_many(
        sender=sender,
        send_pairs=send_pairs,
        cur=cur,
        fee_coin_id=0,
        gas_price=gas_price,
        msg_type=C.MSG_MSGPACK,
        msg_body=msg_body,
        retention=retention)
    return tx


def create_contract_update_tx(c_address,
                              cur,
                              c_bin=None,
                              c_extra_imports=None,
                              c_settings=None,
                              send_pairs=None,
                              sender=C.ANT_UNKNOWN,
                              gas_price=None,
                              retention=10800):
    assert c_bin or c_extra_imports or c_settings
    c_method = contract.M_UPDATE
    c_args = (c_bin, c_extra_imports, c_settings)
    redeem_address = create_new_user_keypair(sender, cur, True)
    msg_body = msgpack.packb((c_address, c_method, redeem_address, c_args), use_bin_type=True)
    send_pairs = send_pairs_format_check(c_address=c_address, send_pairs=send_pairs)
    tx = send_many(
        sender=sender,
        send_pairs=send_pairs,
        cur=cur,
        fee_coin_id=0,
        gas_price=gas_price,
        msg_type=C.MSG_MSGPACK,
        msg_body=msg_body,
        retention=retention)
    return tx


def create_contract_transfer_tx(c_address,
                                cur,
                                c_method,
                                c_args=None,
                                send_pairs=None,
                                sender=C.ANT_UNKNOWN,
                                gas_price=None,
                                retention=10800):
    assert isinstance(c_method, str)
    if c_args is None:
        c_args = tuple()
    else:
        c_args = tuple(c_args)
    redeem_address = create_new_user_keypair(sender, cur, True)
    msg_body = msgpack.packb((c_address, c_method, redeem_address, c_args), use_bin_type=True)
    send_pairs = send_pairs_format_check(c_address=c_address, send_pairs=send_pairs)
    tx = send_many(
        sender=sender,
        send_pairs=send_pairs,
        cur=cur,
        fee_coin_id=0,
        gas_price=gas_price,
        msg_type=C.MSG_MSGPACK,
        msg_body=msg_body,
        retention=retention)
    return tx


def create_conclude_tx(c_address, start_tx, redeem_address, send_pairs=None, c_storage=None, emulate_gas=0):
    assert isinstance(start_tx, TX)
    assert send_pairs is None or isinstance(send_pairs, list)
    assert c_storage is None or isinstance(c_storage, dict)
    assert isinstance(emulate_gas, int)
    message = msgpack.packb((c_address, start_tx.hash, c_storage), use_bin_type=True)
    v = get_validator_by_contract_info(c_address=c_address, start_tx=start_tx)
    send_pairs = send_pairs or list()
    tx = TX.from_dict(
        tx={
            'type': C.TX_CONCLUDE_CONTRACT,
            'time': start_tx.time,
            'deadline': start_tx.deadline,
            'gas_price': start_tx.gas_price,
            'gas_amount': 0,
            'outputs': [tuple(s) for s in send_pairs],
            'message_type': C.MSG_MSGPACK,
            'message': message
        })
    tx.gas_amount = tx.size
    # fill unspents
    fill_inputs_outputs(tx=tx, target_address=(c_address,), signature_num=v.require)
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
            raise BlockChainError('Cannot move conclude fee, add={} sub={}'.format(f_finish_add, f_finish_sub))
        log.debug("Move conclude fee {}:{}".format(fee_coin_id, conclude_fee))
    tx.serialize()
    if v.version == -1:
        raise BlockChainError('Not init validator address. {}'.format(c_address))
    if setup_contract_signature(tx, v.validators) == 0:
        raise BlockChainError('Cannot sign, you are not validator.')
    return tx


def create_validator_edit_tx(v_address,
                             cur,
                             new_address=None,
                             flag=F_NOP,
                             sig_diff=0,
                             gas_price=None,
                             retention=10800):
    assert not (flag == F_NOP and sig_diff == 0), 'No edit info.'
    if new_address is None and flag != F_NOP:
        raise BlockChainError('No cosigner edit, but flag is not NOP.')
    # validator object
    v = get_validator_object(v_address=v_address)
    if v.version == -1:
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
    message = msgpack.packb((v_address, new_address, flag, sig_diff), use_bin_type=True)
    tx = TX.from_dict(
        tx={
            'type': C.TX_VALIDATOR_EDIT,
            'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
            'gas_amount': 0,
            'message_type': C.MSG_MSGPACK,
            'message': message
        })
    tx.gas_amount = tx.size
    tx.update_time(retention)
    # fill unspents
    additional_gas = C.VALIDATOR_EDIT_GAS + v.require * C.SIGNATURE_GAS
    input_address = fill_inputs_outputs(tx=tx, cur=cur, additional_gas=additional_gas)
    assert len(input_address & set(v.validators)) == 0, 'Not implemented?'
    # replace dummy address
    replace_redeem_dummy_address(tx=tx, cur=cur)
    setup_signature(tx, input_address)
    if v.version > -1 and setup_contract_signature(tx, v.validators) == 0:
        raise BlockChainError('Cannot sign, you are not validator.')
    return tx


def create_signed_tx_as_validator(tx: TX):
    tx = deepcopy(tx)
    if tx.type == C.TX_VALIDATOR_EDIT:
        v_address, new_address, flag, sig_diff = tx.encoded_message()
        v = get_validator_object(v_address=v_address, stop_txhash=tx.hash)
    elif tx.type == C.TX_CONCLUDE_CONTRACT:
        c_address, start_hash, c_storage = tx.encoded_message()
        v = get_validator_by_contract_info(c_address=c_address, start_hash=start_hash)
    else:
        raise BlockChainError('Not found tx type {}'.format(tx))
    # sign and check how many add signs
    if setup_contract_signature(tx, v.validators) == 0:
        raise BlockChainError('Cannot sign, you are not validator or already signed.')
    return tx


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
    "F_NOP",
    "F_REMOVE",
    "F_ADD",
    "create_conclude_tx",
    "create_validator_edit_tx",
    "create_signed_tx_as_validator",
]
