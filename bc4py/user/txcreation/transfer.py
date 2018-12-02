from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.chain import TX
from bc4py.database.account import insert_log
from bc4py.user import CoinBalance, UserCoins
from bc4py.user.txcreation.utils import *
from nem_ed25519.key import is_address
import time


def send_many(sender, send_pairs, cur, fee_coin_id=0, gas_price=None,
              msg_type=C.MSG_NONE, msg_body=b'', f_balance_check=True, retention=10800):
    assert isinstance(sender, int), 'Sender is user id.'
    assert 0 < len(send_pairs), 'Empty send_pairs.'
    # send_pairs check
    movements = UserCoins()
    outputs = list()
    coins = CoinBalance()
    for address, coin_id, amount in send_pairs:
        assert isinstance(address, str) and len(address) == 40, 'Recipient is 40 letter string.'
        assert isinstance(coin_id, int) and isinstance(amount, int), 'CoinID, amount is int.'
        coins[coin_id] += amount
        outputs.append((address, coin_id, amount))
    movements[sender] -= coins
    movements[C.ANT_OUTSIDE] += coins
    # tx
    now = int(time.time() - V.BLOCK_GENESIS_TIME)
    tx = TX(tx={
        'version': __chain_version__,
        'type': C.TX_TRANSFER,
        'time': now,
        'deadline': now + retention,
        'inputs': list(),
        'outputs': outputs,
        'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
        'gas_amount': 1,
        'message_type': msg_type,
        'message': msg_body})
    tx.gas_amount = tx.size + C.SIGNATURE_GAS
    # fill unspents
    input_address = fill_inputs_outputs(tx, cur, fee_coin_id, additional_gas=0)
    # account check
    fee_coins = CoinBalance(coin_id=fee_coin_id, amount=tx.gas_price * tx.gas_amount)
    if f_balance_check:
        # 残高が十分にあるかチェック
        send_coins = CoinBalance()
        for address, coin_id, amount in send_pairs:
            send_coins[coin_id] += amount
        check_enough_amount(sender, send_coins, fee_coins)
    if sender in (C.ANT_OUTSIDE, C.ANT_RESERVED):
        # 内部アカウントは不可
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


def send_from(sender, address, coins, cur, fee_coin_id=0, gas_price=None,
              msg_type=C.MSG_NONE, msg_body=b'', f_balance_check=True, retention=10800):
    assert isinstance(coins, CoinBalance)
    send_pairs = list()
    for coin_id, amount in coins:
        send_pairs.append((address, coin_id, amount))
    return send_many(sender, send_pairs, cur, fee_coin_id, gas_price, msg_type,
                     msg_body, f_balance_check, retention)


__all__ = [
    "send_from", "send_many"
]
