from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.chain.tx import TX
from bc4py.database.account import insert_movelog, read_address2userid
from bc4py.user import Balance, Accounting
from bc4py.user.txcreation.utils import *
from time import time


def send_many(sender,
              send_pairs,
              cur,
              fee_coin_id=0,
              gas_price=None,
              msg_type=C.MSG_NONE,
              msg_body=b'',
              subtract_fee_from_amount=False,
              retention=10800):
    assert isinstance(sender, int), 'Sender is user id'
    assert 0 < len(send_pairs), 'Empty send_pairs'
    # send_pairs check
    movements = Accounting()
    send_coins = Balance()
    outputs = list()
    coins = Balance()
    for address, coin_id, amount in send_pairs:
        assert isinstance(address, str)
        assert isinstance(coin_id, int) and isinstance(amount, int), 'CoinID, amount is int'
        coins[coin_id] += amount
        outputs.append((address, coin_id, amount))
        user = read_address2userid(address=address, cur=cur)
        if user is not None:
            movements[user][coin_id] += amount  # send to myself
    movements[sender] -= coins
    # movements[C.ANT_OUTSIDE] += coins
    # tx
    now = int(time() - V.BLOCK_GENESIS_TIME)
    tx = TX.from_dict(
        tx={
            'version': __chain_version__,
            'type': C.TX_TRANSFER,
            'time': now,
            'deadline': now + retention,
            'inputs': list(),
            'outputs': outputs,
            'gas_price': gas_price or V.COIN_MINIMUM_PRICE,
            'gas_amount': 1,
            'message_type': msg_type,
            'message': msg_body
        })
    tx.gas_amount = tx.size + C.SIGNATURE_GAS
    # fill unspents
    input_address = fill_inputs_outputs(tx=tx, cur=cur, fee_coin_id=fee_coin_id)
    # subtract fee from amount
    if subtract_fee_from_amount:
        if fee_coin_id != 0:
            raise BlockChainError('subtract_fee option require fee_coin_id=0')
        subtract_fee = subtract_fee_from_user_balance(tx)
        # fee returns to sender's balance
        movements[sender][0] += subtract_fee
        send_coins[0] -= subtract_fee
    fee_coins = Balance(coin_id=fee_coin_id, amount=tx.gas_price * tx.gas_amount)
    # check enough balance account have
    for address, coin_id, amount in send_pairs:
        send_coins[coin_id] += amount
    check_enough_amount(sender=sender, send_coins=send_coins, fee_coins=fee_coins, cur=cur)
    # replace dummy address
    replace_redeem_dummy_address(tx, cur)
    # setup signature
    tx.serialize()
    setup_signature(tx, input_address)
    movements[sender] -= fee_coins
    # movements[C.ANT_OUTSIDE] += fee_coins
    insert_movelog(movements, cur, tx.type, tx.time, tx.hash)
    return tx


def send_from(sender,
              address,
              coins,
              cur,
              fee_coin_id=0,
              gas_price=None,
              msg_type=C.MSG_NONE,
              msg_body=b'',
              subtract_fee_amount=False,
              retention=10800):
    assert isinstance(coins, Balance)
    send_pairs = list()
    for coin_id, amount in coins:
        send_pairs.append((address, coin_id, amount))
    return send_many(sender=sender, send_pairs=send_pairs, cur=cur, fee_coin_id=fee_coin_id,
                     gas_price=gas_price, msg_type=msg_type, msg_body=msg_body,
                     subtract_fee_from_amount=subtract_fee_amount, retention=retention)


def subtract_fee_from_user_balance(tx: TX):
    """subtract fee from user's sending outputs"""
    subtract_fee = tx.gas_amount * tx.gas_price
    f_subtracted = False
    f_added = False
    for index, (address, coin_id, amount) in enumerate(tx.outputs):
        if coin_id != 0:
            continue
        elif amount < subtract_fee:
            continue
        elif not f_added and address == DUMMY_REDEEM_ADDRESS:
            # add used fee to redeem output
            tx.outputs[index] = (address, coin_id, amount + subtract_fee)
            f_added = True
        elif not f_subtracted and address != DUMMY_REDEEM_ADDRESS:
            # subtract used fee from sending output
            tx.outputs[index] = (address, coin_id, amount - subtract_fee)
            f_subtracted = True
        else:
            continue
    # check
    if f_subtracted is False or f_added is False:
        raise BlockChainError('failed to subtract fee sub={} add={} fee={}'
                              .format(f_subtracted, f_added, subtract_fee))
    return subtract_fee


__all__ = [
    "send_from",
    "send_many",
]
