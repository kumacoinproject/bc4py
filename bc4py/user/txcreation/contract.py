from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.chain import TX
from bc4py.chain.utils import check_output_format
from bc4py.database.account import create_new_user_keypair, insert_log
from bc4py.user import CoinObject, UserCoins
from bc4py.user.txcreation.utils import *
import time
import bjson


def create_contract_tx(c_bin, cur, sender=C.ANT_UNKNOWN,
                       c_cs=None, gas_price=None, retention=10800):
    assert isinstance(c_bin, bytes), 'contract is bytes code.'
    assert isinstance(sender, int), 'Sender is id.'
    if c_cs:
        for k, v in c_cs.items():
            assert isinstance(k, bytes), 'Key is bytes.'
            assert isinstance(v, bytes), 'Value is bytes.'
    # TXを作成
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    c_address = create_new_user_keypair(C.ANT_NAME_CONTRACT, cur)
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
    return c_address, tx


def start_contract_tx(c_address, c_data, cur, outputs=None, sender=C.ANT_UNKNOWN,
                      gas_price=None, additional_gas_amount=None, retention=10800):
    # TXを作成
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    c_redeem = create_new_user_keypair(C.ANT_NAME_UNKNOWN, cur)
    message = bjson.dumps((c_address, c_data, c_redeem), compress=False)
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
    return tx
