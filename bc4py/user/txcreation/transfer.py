from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.chain import TX
from bc4py.database.user.flag import is_exist_group
from bc4py.database.user.read import read_balance
from bc4py.user.utxo import get_unspent, full_unspents
from bc4py.user import CoinObject
from bc4py.user.txcreation.utils import *
from nem_ed25519.key import is_address
import time


def sendfrom(from_group, to_address, coins, chain_cur, account_cur, fee_coin_id=0, gas_price=None,
             msg_type=C.MSG_NONE, msg_body=b'', f_balance_check=True,
             f_allow_inner_account=False, retention=10800):
    address_coin_list = list()
    for coin_id, amount in coins.items():
        address_coin_list.append((to_address, coin_id, amount))
    return sendmany(from_group, address_coin_list, chain_cur, account_cur, fee_coin_id,
                    gas_price, msg_type, msg_body, f_balance_check,
                    f_allow_inner_account, retention)


def sendmany(from_group, address_coin_list, chain_cur, account_cur, fee_coin_id=0, gas_price=None,
             msg_type=C.MSG_NONE, msg_body=b'', f_balance_check=True,
             f_allow_inner_account=False, retention=10800):
    gas_price = gas_price if gas_price else V.COIN_MINIMUM_PRICE
    assert gas_price >= V.COIN_MINIMUM_PRICE, 'Too low gas price {}>={}'.format(gas_price, V.COIN_MINIMUM_PRICE)
    assert 0 < len(address_coin_list), 'Empty address_coin_list.'

    for address, coin_id, amount in address_coin_list:
        # アドレスチェック
        if not is_address(ck=address, prefix=V.BLOCK_PREFIX):
            raise BlockChainError('Is not normal address. {}'.format(address))

    # TXを作成
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    tx = TX(tx={
        'version': __chain_version__,
        'type': C.TX_TRANSFER,
        'time': now,
        'deadline': now + retention,
        'inputs': list(),
        'outputs': address_coin_list.copy(),
        'gas_price': gas_price,
        'gas_amount': 1,
        'message_type': msg_type,
        'message': msg_body})
    # 全てのUnspentを取得
    unspent_pairs, orphan_pairs = get_unspent(chain_cur=chain_cur, account_cur=account_cur)
    unspents = full_unspents(unspent_pairs, chain_cur)
    # input/outputを補充
    input_address = fill_inputs_outputs(tx, unspents, chain_cur, fee_coin_id)
    # Outputsの攪拌
    randomize_output(tx, fee_coin_id)

    # アカウントチェック
    if f_balance_check:
        # 残高が十分にあるかチェック
        from_coins = read_balance(group=from_group, cur=account_cur)
        fee_coins = CoinObject(coin_id=fee_coin_id, amount=tx.gas_price * tx.gas_amount)
        send_coins = CoinObject()
        for address, coin_id, amount in address_coin_list:
            send_coins[coin_id] += amount
        remain_coins = from_coins - send_coins - fee_coins
        if not remain_coins.is_all_plus_amount():
            raise BlockChainError('Not enough balance in {}.'.format(from_group))
    elif not f_allow_inner_account and from_group in (C.ANT_OUTSIDE, C.ANT_RESERVED):
        # 内部アカウントは不可
        raise BlockChainError('Not allowed inner account.')
    elif not is_exist_group(group=from_group, cur=account_cur):
        # 存在しないユーザー
        raise BlockChainError('Not found group {}.'.format(from_group))

    # RedeemDummyAddressを入れ替え
    new_redeem_address = replace_redeem_dummy_address(tx, account_cur)
    # Account間の移動をログに記録
    tx.serialize()
    recode_account_movement(tx, new_redeem_address, from_group, chain_cur, account_cur)
    # 署名をする
    setup_signature(tx, input_address)
    return tx
