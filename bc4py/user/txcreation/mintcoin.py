from bc4py.config import C, V, BlockChainError
from bc4py.bip32 import dummy_address
from bc4py.chain.tx import TX
from bc4py.database.mintcoin import *
from bc4py.database.account import generate_new_address_by_userid, insert_movelog
from bc4py.user import Balance, Accounting
from bc4py.user.txcreation.utils import *
import random
import msgpack

MINTCOIN_DUMMY_ADDRESS = dummy_address(b'MINTCOIN_DUMMY_ADDR_')


def issue_mint_coin(name,
                    unit,
                    digit,
                    amount,
                    cur,
                    description=None,
                    image=None,
                    additional_issue=True,
                    change_address=True,
                    gas_price=None,
                    sender=C.ANT_UNKNOWN,
                    retention=10800):
    mint_id = get_new_coin_id()
    mint_address = generate_new_address_by_userid(user=sender, cur=cur)
    params = {
        "name": name,
        "unit": unit,
        "digit": digit,
        "address": mint_address,
        "description": description,
        "image": image
    }
    setting = {"additional_issue": additional_issue, "change_address": change_address}
    m_before = get_mintcoin_object(coin_id=mint_id)
    result = check_mintcoin_new_format(m_before=m_before, new_params=params, new_setting=setting)
    if isinstance(result, str):
        raise BlockChainError('check_mintcoin_new_format(): {}'.format(result))
    msg_body = msgpack.packb((mint_id, params, setting), use_bin_type=True)
    tx = TX.from_dict(
        tx={
            'type': C.TX_MINT_COIN,
            'inputs': list(),
            'outputs': [(MINTCOIN_DUMMY_ADDRESS, 0, amount)],
            'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
            'gas_amount': 1,
            'message_type': C.MSG_MSGPACK,
            'message': msg_body
        })
    tx.update_time(retention)
    additional_gas = C.MINTCOIN_GAS
    tx.gas_amount = tx.size + C.SIGNATURE_GAS + additional_gas
    tx.serialize()
    # fill unspents
    fee_coin_id = 0
    input_address = fill_inputs_outputs(tx=tx, cur=cur, fee_coin_id=fee_coin_id, additional_gas=additional_gas)
    # input_address.add(mint_address)
    fee_coins = Balance(coin_id=fee_coin_id, amount=tx.gas_price * tx.gas_amount)
    # check amount
    check_enough_amount(sender=sender, send_coins=Balance(0, amount), fee_coins=fee_coins, cur=cur)
    # replace dummy address
    replace_redeem_dummy_address(tx=tx, cur=cur)
    # replace dummy mint_id
    replace_mint_dummy_address(tx=tx, mint_address=mint_address, mint_id=mint_id, f_raise=True)
    # setup signature
    tx.serialize()
    setup_signature(tx=tx, input_address=input_address)
    # movement
    movements = Accounting()
    minting_coins = Balance(mint_id, amount)
    movements[sender] += minting_coins
    # movements[C.ANT_OUTSIDE] -= minting_coins
    movements[sender] -= fee_coins
    # movements[C.ANT_OUTSIDE] += fee_coins
    insert_movelog(movements, cur, tx.type, tx.time, tx.hash)
    return mint_id, tx


def change_mint_coin(mint_id,
                     cur,
                     amount=None,
                     description=None,
                     image=None,
                     setting=None,
                     new_address=None,
                     gas_price=None,
                     sender=C.ANT_UNKNOWN,
                     retention=10800):
    assert amount or description or image or setting or new_address
    params = dict()
    if description:
        params['description'] = description
    if image:
        params['image'] = image
    if new_address:
        params['address'] = new_address
    if len(params) == 0:
        params = None
    if not params and not setting and not amount:
        raise BlockChainError('No update found')
    m_before = get_mintcoin_object(coin_id=mint_id)
    if m_before.version == -1:
        raise BlockChainError('Not init mintcoin. {}'.format(m_before))
    result = check_mintcoin_new_format(m_before=m_before, new_params=params, new_setting=setting)
    if isinstance(result, str):
        raise BlockChainError('check_mintcoin_new_format(): {}'.format(result))
    msg_body = msgpack.packb((mint_id, params, setting), use_bin_type=True)
    tx = TX.from_dict(
        tx={
            'type': C.TX_MINT_COIN,
            'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
            'gas_amount': 1,
            'message_type': C.MSG_MSGPACK,
            'message': msg_body
        })
    if amount:
        tx.outputs.append((MINTCOIN_DUMMY_ADDRESS, 0, amount))
        send_coins = Balance(0, amount)
        minting_coins = Balance(mint_id, amount)
    else:
        send_coins = Balance(0, 0)
        minting_coins = Balance(0, 0)
    tx.update_time(retention)
    additional_gas = C.MINTCOIN_GAS + C.SIGNATURE_GAS  # for mint_coin user signature
    tx.gas_amount = tx.size + C.SIGNATURE_GAS + additional_gas
    tx.serialize()
    # fill unspents
    fee_coin_id = 0
    input_address = fill_inputs_outputs(tx=tx, cur=cur, fee_coin_id=fee_coin_id, additional_gas=additional_gas)
    input_address.add(m_before.address)
    fee_coins = Balance(coin_id=fee_coin_id, amount=tx.gas_price * tx.gas_amount)
    # check amount
    check_enough_amount(sender=sender, send_coins=send_coins, fee_coins=fee_coins, cur=cur)
    # replace dummy address
    replace_redeem_dummy_address(tx=tx, cur=cur)
    # replace dummy mint_id
    replace_mint_dummy_address(tx=tx, mint_address=m_before.address, mint_id=mint_id, f_raise=False)
    # setup signature
    tx.serialize()
    setup_signature(tx=tx, input_address=input_address)
    # movement
    movements = Accounting()
    movements[sender] += minting_coins
    # movements[C.ANT_OUTSIDE] -= minting_coins
    movements[sender] -= fee_coins
    # movements[C.ANT_OUTSIDE] += fee_coins
    insert_movelog(movements, cur, tx.type, tx.time, tx.hash)
    return tx


def get_new_coin_id():
    while True:
        coin_id = random.randint(1, 0xffffffff)
        if get_mintcoin_object(coin_id).version == -1:
            return coin_id


def replace_mint_dummy_address(tx, mint_address, mint_id, f_raise):
    for index, (address, coin_id, amount) in enumerate(tx.outputs):
        if address == MINTCOIN_DUMMY_ADDRESS:
            tx.outputs[index] = (mint_address, mint_id, amount)
            break
    else:
        if f_raise:
            raise BlockChainError('Cannot replace Mintcoin dummy address')


__all__ = [
    "issue_mint_coin",
    "change_mint_coin",
]
