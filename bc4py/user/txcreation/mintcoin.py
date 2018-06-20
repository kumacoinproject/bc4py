from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.chain import TX
from bc4py.chain.mintcoin import MintCoinObject
from bc4py.database.tools import get_mintcoin
from bc4py.database.account import create_new_user_keypair, read_address2keypair, insert_log
from bc4py.user import CoinObject, UserCoins
from bc4py.user.txcreation.utils import *
from nem_ed25519.key import get_address
import random
import logging
import time


MINTCOIN_DUMMY_ADDRESS = '_____MINTCOIN_____DUMMY_____ADDRESS_____'


def issue_mintcoin(name, unit, amount, digit, cur, gas_price=None,
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
    movements[sender] -= minting_coins
    movements[C.ANT_OUTSIDE] += minting_coins
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
    tx.gas_amount = tx.getsize() + 96 + C.MINTCOIN_FEE
    tx.serialize()
    # fill unspents
    fee_coin_id = 0
    input_address = fill_inputs_outputs(tx, cur, fee_coin_id, C.MINTCOIN_FEE)
    fee_coins = CoinObject(fee_coin_id, tx.gas_price*tx.gas_amount)
    # check amount
    check_enough_amount(sender, minting_coins, fee_coins)
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
    return mint, tx


def change_mintcoin(mint_id, cur, amount=0, message=None,
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
    movements[sender] -= minting_coins
    movements[C.ANT_OUTSIDE] += minting_coins
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
    tx.gas_amount = tx.getsize() + 96 + C.MINTCOIN_FEE
    tx.serialize()
    fee_coin_id = 0
    input_address = fill_inputs_outputs(tx, cur, fee_coin_id, C.MINTCOIN_FEE)
    fee_coins = CoinObject(fee_coin_id, tx.gas_price * tx.gas_amount)
    # check amount
    check_enough_amount(sender, minting_coins, fee_coins)
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
    return mint_new, tx


def get_new_coin_id():
    while True:
        coin_id = random.randint(1, 0xffffffff)
        if get_mintcoin(coin_id) is None:
            return coin_id


def replace_mint_dummy_address(tx, mint_address, mint_id):
    for index, (address, coin_id, amount) in enumerate(tx.outputs):
        if address == MINTCOIN_DUMMY_ADDRESS:
            tx.outputs[index] = (mint_address, mint_id, amount)
            break
    else:
        raise BlockChainError('Cannot replace Mintcoin dummy address.')


__all__ = [
    "issue_mintcoin",
    "change_mintcoin"
]
