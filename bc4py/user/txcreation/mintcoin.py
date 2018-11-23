from bc4py.config import C, V, BlockChainError
from bc4py.chain import TX
from bc4py.database.mintcoin import *
from bc4py.database.account import create_new_user_keypair, insert_log
from bc4py.user import CoinObject, UserCoins
from bc4py.user.txcreation.utils import *
import random
import bjson
from binascii import hexlify


MINTCOIN_DUMMY_ADDRESS = '_____MINTCOIN_____DUMMY_____ADDRESS_____'


def issue_mintcoin(name, unit, digit, amount, cur, description=None, image=None, additional_issue=True,
                   change_address=True, gas_price=None, sender=C.ANT_UNKNOWN, retention=10800):
    mint_id = get_new_coin_id()
    mint_address = create_new_user_keypair(name=sender, cur=cur)
    params = {"name": name, "unit": unit, "digit": digit,
              "address": mint_address, "description": description, "image": image}
    setting = {"additional_issue": additional_issue, "change_address": change_address}
    m_before = get_mintcoin_object(coin_id=mint_id)
    result = check_mintcoin_new_format(m_before=m_before, new_params=params, new_setting=setting)
    if isinstance(result, str):
        raise BlockChainError('check_mintcoin_new_format(): {}'.format(result))
    msg_body = bjson.dumps((mint_id, params, setting), compress=False)
    tx = TX(tx={
        'type': C.TX_MINT_COIN,
        'inputs': list(),
        'outputs': [(MINTCOIN_DUMMY_ADDRESS, 0, amount)],
        'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
        'gas_amount': 1,
        'message_type': C.MSG_BYTE,
        'message': msg_body})
    tx.update_time(retention)
    tx.gas_amount = tx.getsize() + C.MINTCOIN_GAS
    tx.serialize()
    # fill unspents
    fee_coin_id = 0
    additional_gas = C.MINTCOIN_GAS + 96
    input_address = fill_inputs_outputs(tx=tx, cur=cur, fee_coin_id=fee_coin_id, additional_gas=additional_gas)
    # input_address.add(mint_address)
    fee_coins = CoinObject(coin_id=fee_coin_id, amount=tx.gas_price * tx.gas_amount)
    # check amount
    check_enough_amount(sender=sender, send_coins=CoinObject(0, amount), fee_coins=fee_coins)
    # replace dummy address
    replace_redeem_dummy_address(tx=tx, cur=cur)
    # replace dummy mint_id
    replace_mint_dummy_address(tx=tx, mint_address=mint_address, mint_id=mint_id, f_raise=True)
    # setup signature
    tx.serialize()
    setup_signature(tx=tx, input_address=input_address)
    # movement
    movements = UserCoins()
    minting_coins = CoinObject(mint_id, amount)
    movements[sender] += minting_coins
    movements[C.ANT_OUTSIDE] -= minting_coins
    movements[sender] -= fee_coins
    movements[C.ANT_OUTSIDE] += fee_coins
    insert_log(movements, cur, tx.type, tx.time, tx.hash)
    return mint_id, tx


"""def issue_mintcoin_old(name, unit, amount, digit, cur, gas_price=None,
                   message='', additional_issue=True, image=None, sender=C.ANT_UNKNOWN):
    mint = MintCoinObject(None)
    new_mint_id = get_new_coin_id()
    mint.version = 0
    mint.coin_id = new_mint_id
    mint.name = name
    mint.unit = unit
    mint.digit = digit
    mint.supply_before = 0
    mint.amount = amount
    mint.additional_issue = additional_issue
    new_mint_address = create_new_user_keypair(C.ANT_NAME_UNKNOWN, cur)
    uuid, sk, pk = read_address2keypair(new_mint_address, cur)
    mint.owner = pk
    mint.image = image
    mint.message = message
    # Message内署名
    mint.generate_sign(sk)
    mint.serialize()
    mint.check_param()
    mint.check_sign()
    logging.info("New Mintcoin skeleton created coin_id={}".format(mint.coin_id))
    # movement
    movements = UserCoins()
    minting_coins = CoinObject(new_mint_id, amount)
    movements[sender] += minting_coins
    movements[C.ANT_OUTSIDE] -= minting_coins
    # TXを作成する
    base_coin_id = 0
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    tx = TX(tx={
        'version': __chain_version__,
        'type': C.TX_MINT_COIN,
        'time': now,
        'deadline': now + 10800,
        'inputs': list(),
        'outputs': [(MINTCOIN_DUMMY_ADDRESS, base_coin_id, amount)],
        'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
        'gas_amount': 1,
        'message_type': C.MSG_BYTE,
        'message': mint.binary})
    tx.gas_amount = tx.getsize() + 96 + C.MINTCOIN_GAS
    tx.serialize()
    # fill unspents
    fee_coin_id = 0
    input_address = fill_inputs_outputs(tx, cur, fee_coin_id, C.MINTCOIN_GAS)
    fee_coins = CoinObject(fee_coin_id, tx.gas_price*tx.gas_amount)
    # check amount
    check_enough_amount(sender, CoinObject(base_coin_id, amount), fee_coins)
    # replace dummy address
    replace_redeem_dummy_address(tx, cur)
    # replace dummy mint_id
    replace_mint_dummy_address(tx, new_mint_address, new_mint_id)
    # setup signature
    tx.serialize()
    setup_signature(tx, input_address)
    movements[sender] -= fee_coins
    movements[C.ANT_OUTSIDE] += fee_coins
    insert_log(movements, cur, tx.type, tx.time, tx.hash)
    return mint, tx"""


def change_mintcoin(mint_id, cur, amount=None, description=None, image=None, setting=None, new_address=None,
                    gas_price=None, sender=C.ANT_UNKNOWN, retention=10800):
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
        raise BlockChainError('No update found.')
    m_before = get_mintcoin_object(coin_id=mint_id)
    if m_before.version == -1:
        raise BlockChainError('Not init mintcoin. {}'.format(m_before))
    result = check_mintcoin_new_format(m_before=m_before, new_params=params, new_setting=setting)
    if isinstance(result, str):
        raise BlockChainError('check_mintcoin_new_format(): {}'.format(result))
    msg_body = bjson.dumps((mint_id, params, setting), compress=False)
    tx = TX(tx={
        'type': C.TX_MINT_COIN,
        'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
        'gas_amount': 1,
        'message_type': C.MSG_BYTE,
        'message': msg_body})
    if amount:
        tx.outputs.append((MINTCOIN_DUMMY_ADDRESS, 0, amount))
        send_coins = CoinObject(0, amount)
        minting_coins = CoinObject(mint_id, amount)
    else:
        send_coins = CoinObject(0, 0)
        minting_coins = CoinObject(0, 0)
    tx.update_time(retention)
    tx.gas_amount = tx.getsize() + C.MINTCOIN_GAS
    tx.serialize()
    # fill unspents
    fee_coin_id = 0
    additional_gas = C.MINTCOIN_GAS + 96
    input_address = fill_inputs_outputs(tx=tx, cur=cur, fee_coin_id=fee_coin_id, additional_gas=additional_gas)
    input_address.add(m_before.address)
    fee_coins = CoinObject(coin_id=fee_coin_id, amount=tx.gas_price * tx.gas_amount)
    # check amount
    check_enough_amount(sender=sender, send_coins=send_coins, fee_coins=fee_coins)
    # replace dummy address
    replace_redeem_dummy_address(tx=tx, cur=cur)
    # replace dummy mint_id
    replace_mint_dummy_address(tx=tx, mint_address=m_before.address, mint_id=mint_id, f_raise=False)
    # setup signature
    tx.serialize()
    setup_signature(tx=tx, input_address=input_address)
    # movement
    movements = UserCoins()
    movements[sender] += minting_coins
    movements[C.ANT_OUTSIDE] -= minting_coins
    movements[sender] -= fee_coins
    movements[C.ANT_OUTSIDE] += fee_coins
    insert_log(movements, cur, tx.type, tx.time, tx.hash)
    return tx


"""def change_mintcoin_old(mint_id, cur, amount=0, message=None,
                    additional_issue=None, image=None, sender=C.ANT_UNKNOWN):
    mint_old = get_mintcoin(mint_id)
    assert mint_old, 'Not defined MintCoin {}'.format(mint_id)
    mint_new = MintCoinObject(None)
    mint_new.version = mint_old.version + 1
    mint_new.coin_id = mint_id
    mint_new.amount = amount
    mint_new.additional_issue = additional_issue
    mint_address = get_address(mint_old.owner, prefix=V.BLOCK_PREFIX)
    uuid, sk, pk = read_address2keypair(mint_address, cur)
    mint_new.owner = pk
    mint_new.image = image
    mint_new.message = message
    # マージチェック
    mint_new.marge(mint_old)
    # Message内署名
    mint_new.generate_sign(sk)
    mint_new.serialize()
    mint_new.check_param()
    mint_new.check_sign()
    logging.info("New Mintcoin skeleton created coin_id={}".format(mint_new.coin_id))
    # movement
    movements = UserCoins()
    minting_coins = CoinObject(mint_id, amount)
    movements[sender] += minting_coins
    movements[C.ANT_OUTSIDE] -= minting_coins
    # TXを作成する
    base_coin_id = 0
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    tx = TX(tx={
        'version': __chain_version__,
        'type': C.TX_MINT_COIN,
        'time': now,
        'deadline': now + 10800,
        'inputs': list(),
        'outputs': [(MINTCOIN_DUMMY_ADDRESS, base_coin_id, amount)] if 0 < amount else list(),
        'gas_price': V.COIN_MINIMUM_PRICE,
        'gas_amount': 1,
        'message_type': C.MSG_BYTE,
        'message': mint_new.binary})
    tx.gas_amount = tx.getsize() + 96 + C.MINTCOIN_GAS
    tx.serialize()
    fee_coin_id = 0
    input_address = fill_inputs_outputs(tx, cur, fee_coin_id, C.MINTCOIN_GAS)
    fee_coins = CoinObject(fee_coin_id, tx.gas_price * tx.gas_amount)
    # check amount
    check_enough_amount(sender, CoinObject(base_coin_id, amount), fee_coins)
    # replace dummy address
    replace_redeem_dummy_address(tx, cur)
    # replace dummy mint_id
    if amount > 0:
        replace_mint_dummy_address(tx, mint_address, mint_id)
    # setup signature
    tx.serialize()
    setup_signature(tx, input_address)
    movements[sender] -= fee_coins
    movements[C.ANT_OUTSIDE] += fee_coins
    insert_log(movements, cur, tx.type, tx.time, tx.hash)
    return mint_new, tx"""


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
            raise BlockChainError('Cannot replace Mintcoin dummy address.')


__all__ = [
    "issue_mintcoin",
    "change_mintcoin"
]
