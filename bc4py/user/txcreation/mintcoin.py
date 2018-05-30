from bc4py.config import C, V, BlockChainError
from bc4py.chain import TX
from bc4py.chain.mintcoin import MintCoinObject
from bc4py.database.chain.read import read_mint_coin
from bc4py.database.user.read import address2keypair
from bc4py.user.account import create_new_group_keypair
from bc4py.user.txcreation.utils import *
from bc4py.user.utxo import get_unspent, full_unspents
from nem_ed25519.key import get_address
import random
import logging
import time


MINTCOIN_DUMMY_ADDRESS = '_____MINTCOIN_____DUMMY_____ADDRESS_____'


def issue_mintcoin(name, unit, amount, digit, chain_cur, account_cur,
                   message='', additional_issue=True, image=None, from_group=C.ANT_UNKNOWN):
    mint = MintCoinObject(None)
    mint_id = get_new_coin_id(chain_cur=chain_cur)
    mint.version = 0
    mint.coin_id = mint_id
    mint.name = name
    mint.unit = unit
    mint.digit = digit
    mint.supply_before = 0
    mint.amount = amount
    mint.additional_issue = additional_issue
    mint_address = create_new_group_keypair(group=from_group, account_cur=account_cur)
    sk, pk = address2keypair(address=mint_address, cur=account_cur)
    mint.owner = pk
    mint.image = image
    mint.message = message
    # Message内署名
    mint.generate_sign(sk)
    mint.serialize()
    mint.check_param()
    mint.check_sign()
    logging.info("New Mintcoin skeleton created coin_id={}".format(mint.coin_id))
    # TXを作成する
    base_coin_id = 0
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    tx = TX(tx={
        'version': 1,
        'type': C.TX_MINT_COIN,
        'time': now,
        'deadline': now + 10800,
        'inputs': list(),
        'outputs': [(MINTCOIN_DUMMY_ADDRESS, base_coin_id, amount)],
        'gas_price': V.COIN_MINIMUM_PRICE,
        'gas_amount': 0,
        'message_type': C.MSG_BYTE,
        'message': mint.binary})
    tx.gas_amount = tx.getsize() + 96 + C.MINTCOIN_FEE
    tx.serialize()
    # 全てのUnspentを取得
    unspent_pairs, orphan_pairs = get_unspent(chain_cur=chain_cur, account_cur=account_cur)
    unspents = full_unspents(unspent_pairs, chain_cur)
    # input/outputを補充
    input_address = fill_inputs_outputs(tx, unspents, chain_cur, base_coin_id, C.MINTCOIN_FEE)
    # RedeemDummyAddressを入れ替え
    new_redeem_address = replace_redeem_dummy_address(tx, account_cur)
    # mint_idを入れ替え
    replace_mint_dummy_address(tx, mint_address, mint_id)
    # Account間の移動をログに記録
    tx.serialize()
    recode_account_movement(tx, new_redeem_address, from_group, chain_cur, account_cur)
    # 署名をする
    setup_signature(tx, input_address)
    return mint, tx


def change_mintcoin(mint_id, chain_cur, account_cur,
                    amount=0, message=None, additional_issue=None, image=None, from_group=C.ANT_UNKNOWN):
    mint_old = read_mint_coin(mint_id, chain_cur)
    if mint_old is None:
        raise BlockChainError('Not found mintcoin_id {}'.format(mint_id))
    mint_new = MintCoinObject(None)
    mint_new.version = mint_old.version + 1
    mint_new.coin_id = mint_id
    mint_new.amount = amount
    mint_new.additional_issue = additional_issue
    mint_address = get_address(mint_old.owner, prefix=V.BLOCK_PREFIX)
    sk, pk = address2keypair(address=mint_address, cur=account_cur)
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
    # TXを作成する
    base_coin_id = 0
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    tx = TX(tx={
        'version': 1,
        'type': C.TX_MINT_COIN,
        'time': now,
        'deadline': now + 10800,
        'inputs': list(),
        'outputs': [(MINTCOIN_DUMMY_ADDRESS, base_coin_id, amount)] if 0 < amount else list(),
        'gas_price': V.COIN_MINIMUM_PRICE,
        'gas_amount': 0,
        'message_type': C.MSG_BYTE,
        'message': mint_new.binary})
    tx.gas_amount = tx.getsize() + 96 + C.MINTCOIN_FEE
    tx.serialize()
    # 全てのUnspentを取得
    unspent_pairs, orphan_pairs = get_unspent(chain_cur=chain_cur, account_cur=account_cur)
    unspents = full_unspents(unspent_pairs, chain_cur)
    # input/outputを補充
    input_address = fill_inputs_outputs(tx, unspents, chain_cur, base_coin_id, C.MINTCOIN_FEE)
    # RedeemDummyAddressを入れ替え
    new_redeem_address = replace_redeem_dummy_address(tx, account_cur)
    # mint_idを入れ替え
    if amount > 0:
        replace_mint_dummy_address(tx, mint_address, mint_id)
    # Account間の移動をログに記録
    tx.serialize()
    recode_account_movement(tx, new_redeem_address, from_group, chain_cur, account_cur)
    # 署名をする
    setup_signature(tx, input_address)
    return mint_new, tx


def get_new_coin_id(chain_cur):
    while True:
        coin_id = random.randint(1, 0xffffffff)
        if read_mint_coin(coin_id=coin_id, cur=chain_cur) is None:
            return coin_id


def replace_mint_dummy_address(tx, mint_address, mint_id):
    for index, (address, coin_id, amount) in enumerate(tx.outputs):
        if address == MINTCOIN_DUMMY_ADDRESS:
            tx.outputs[index] = (mint_address, mint_id, amount)
            break
    else:
        raise BlockChainError('Cannot replace Mintcoin dummy address.')
