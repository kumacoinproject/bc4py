from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.chain import TX
from bc4py.chain.utils import check_output_format
from bc4py.database import contract
from bc4py.database.account import create_new_user_keypair, insert_log
from bc4py.database.validator import F_NOP, F_REMOVE, F_ADD, get_validator_object
from bc4py.database.builder import tx_builder
from bc4py.user import CoinObject, UserCoins
from bc4py.user.txcreation.utils import *
from bc4py.user.txcreation.transfer import send_many
from nem_ed25519.key import convert_address
import time
import bjson
from copy import deepcopy


def create_init_contract_tx(c_address, c_bin, cur, c_extra_imports=None, c_settings=None,
                            sender=C.ANT_UNKNOWN, gas_price=None, retention=10800):
    if sender in (C.ANT_OUTSIDE, C.ANT_RESERVED):
        raise BlockChainError('Not allowed inner account.')
    # [c_address]-[c_method]-[c_args]
    c_method = contract.M_INIT
    if c_extra_imports is None:
        c_extra_imports = []
    if c_settings is None:
        c_settings = {'f_update_bin': False}
    c_args = (c_bin, c_extra_imports, c_settings)
    msg_body = bjson.dumps((c_address, c_method, c_args), compress=False)
    send_pairs = [(c_address, 0, C.CONTRACT_MINIMUM_INPUT)]
    tx = send_many(sender=sender, send_pairs=send_pairs, cur=cur, fee_coin_id=0, gas_price=gas_price,
                   msg_type=C.MSG_BYTE, msg_body=msg_body, retention=retention)
    return tx


def create_update_contract_tx(sender=C.ANT_UNKNOWN, gas_price=None, retention=10800):
    pass


def create_contract_transfer_tx(sender=C.ANT_UNKNOWN, gas_price=None, retention=10800):
    pass


def create_validator_edit_tx(c_address, cur, new_address=None,
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
    message = bjson.dumps((c_address, new_address, flag, sig_diff), compress=F_NOP)
    tx = TX(tx={
        'type': C.TX_VALIDATOR_EDIT,
        'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
        'gas_amount': 0,
        'message_type': C.MSG_BYTE,
        'message': message})
    extra_gas = C.VALIDATOR_EDIT_GAS + (C.SIGNATURE_GAS + 96) * v.require
    tx.gas_amount = tx.getsize() + extra_gas
    tx.update_time(retention)
    # fill unspents
    fee_coin_id = 0
    fill_contract_inputs_outputs(tx=tx, c_address=c_address, cur=cur,
                                 fee_coin_id=fee_coin_id, additional_gas=extra_gas)
    # replace dummy address
    replace_redeem_dummy_address(tx=tx, cur=cur, replace_by=c_address)
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
        raise BlockChainError('Cannot sign, you are not validator.')
    return copied_tx


"""def create_contract_tx(c_bin, cur, sender=C.ANT_UNKNOWN,
                       c_cs=None, gas_price=None, retention=10800):
    assert isinstance(c_bin, bytes), 'contract is bytes code.'
    assert isinstance(sender, int), 'Sender is id.'
    if c_cs:
        for k, v in c_cs.items():
            assert isinstance(k, bytes), 'Key is bytes.'
            assert isinstance(v, bytes), 'Value is bytes.'
    # TXを作成
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    ck = create_new_user_keypair(C.ANT_NAME_CONTRACT, cur)
    c_address = convert_address(ck, V.BLOCK_CONTRACT_PREFIX)
    message = bjson.dumps((c_address, c_bin, c_cs), compress=False)
    tx = TX(tx={
        'version': __chain_version__,
        'type': C.TX_CREATE_CONTRACT,
        'time': now,
        'deadline': now + retention,
        'inputs': list(),
        'outputs': list(),
        'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
        'gas_amount': 1,
        'message_type': C.MSG_BYTE,
        'message': message})
    tx.gas_amount = tx.getsize() + C.CONTRACT_CREATE_FEE + 96
    # fill unspents
    fee_coin_id = 0
    input_address = fill_inputs_outputs(tx, cur, fee_coin_id, C.CONTRACT_CREATE_FEE)
    fee_coins = CoinObject(fee_coin_id, tx.gas_price * tx.gas_amount)
    movements = UserCoins()
    movements[sender] -= fee_coins
    movements[C.ANT_OUTSIDE] += fee_coins
    # account check
    send_coins = CoinObject()
    check_enough_amount(sender, send_coins, fee_coins)
    if sender in (C.ANT_OUTSIDE, C.ANT_RESERVED):
        raise BlockChainError('Not allowed inner account.')
    # replace dummy address
    replace_redeem_dummy_address(tx, cur)
    # setup signature
    tx.serialize()
    setup_signature(tx, input_address)
    movements[sender] -= fee_coins
    movements[C.ANT_OUTSIDE] += fee_coins
    insert_log(movements, cur, tx.type, tx.time, tx.hash)
    return c_address, tx"""

"""def start_contract_tx(c_address, c_method, cur, c_args=None, outputs=None, sender=C.ANT_UNKNOWN,
                      gas_price=None, additional_gas_amount=None, retention=10800):
    # TXを作成
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    c_redeem = create_new_user_keypair(C.ANT_NAME_UNKNOWN, cur)
    message = bjson.dumps((c_address, c_method, c_args or tuple(), c_redeem), compress=False)
    tx = TX(tx={
        'version': __chain_version__,
        'type': C.TX_START_CONTRACT,
        'time': now,
        'deadline': now + retention,
        'inputs': list(),
        'outputs': outputs or list(),
        'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
        'gas_amount': 1,
        'message_type': C.MSG_BYTE,
        'message': message})
    check_output_format(tx.outputs)
    tx.gas_amount = tx.getsize() + 96
    tx.serialize()
    # fill unspents
    fee_coin_id = 0
    input_address = fill_inputs_outputs(tx, cur, fee_coin_id, additional_gas_amount or V.CONTRACT_MINIMUM_AMOUNT)
    fee_coins = CoinObject(fee_coin_id, tx.gas_price * tx.gas_amount)
    movements = UserCoins()
    movements[sender] -= fee_coins
    movements[C.ANT_OUTSIDE] += fee_coins
    # account check
    send_coins = CoinObject()
    check_enough_amount(sender, send_coins, fee_coins)
    if sender in (C.ANT_OUTSIDE, C.ANT_RESERVED):
        raise BlockChainError('Not allowed inner account.')
    # replace dummy address
    replace_redeem_dummy_address(tx, cur)
    # setup signature
    tx.serialize()
    setup_signature(tx, input_address)
    movements[sender] -= fee_coins
    movements[C.ANT_OUTSIDE] += fee_coins
    insert_log(movements, cur, tx.type, tx.time, tx.hash)
    return tx"""


__all__ = [
    "create_contract_transfer_tx",
    "create_init_contract_tx",
    "create_update_contract_tx",
    "F_NOP", "F_REMOVE", "F_ADD",
    "create_validator_edit_tx",
    "create_signed_tx_as_validator",
]
