from bc4py.config import C, V, BlockChainError
from bc4py.database.chain.read import read_tx_output
from bc4py.database.user.read import address2group
from bc4py.database.user.write import new_keypair, move_account_balance
from bc4py.user.utils import message2signature
from bc4py.user import CoinObject
import random
import logging


DUMMY_REDEEM_ADDRESS = '_____DUMMY______REDEEM______ADDRESS_____'  # 40letters


def fill_inputs_outputs(tx, unspents, chain_cur, fee_coin_id=0, additional_fee=0):
    assert tx.gas_price > 0, "Gas params is none zero."
    # outputsの合計を取得
    output_coins = CoinObject()
    for address, coin_id, amount in tx.outputs.copy():
        if address == DUMMY_REDEEM_ADDRESS:
            # 償還Outputは再構築するので消す
            tx.outputs.remove((address, coin_id, amount))
            continue
        output_coins[coin_id] += amount
    # 一時的にfeeの概算
    fee_coins = CoinObject(coin_id=fee_coin_id, amount=tx.gas_price*tx.gas_amount)
    # 必要なだけinputsを取得
    tx.inputs.clear()
    tmp_coins = output_coins + fee_coins
    input_coins = CoinObject()
    input_address = set()
    for utxo in unspents:
        if utxo['coin_id'] not in tmp_coins:
            continue
        elif 0 > tmp_coins[utxo['coin_id']]:
            continue
        tmp_coins[utxo['coin_id']] -= utxo['amount']
        input_coins[utxo['coin_id']] += utxo['amount']
        input_address.add(utxo['address'])
        tx.inputs.append((utxo['txhash'], utxo['txindex']))
        if tmp_coins.is_all_minus_amount():
            break
    else:
        raise BlockChainError('Insufficient balance. unspents={} remain={} balance={}'
                              .format(len(unspents), tmp_coins, input_coins))
    # redeemを計算
    redeem_coins = input_coins - output_coins - fee_coins
    for coin_id, amount in redeem_coins.items():
        tx.outputs.append((DUMMY_REDEEM_ADDRESS, coin_id, amount))
    # Feeをチェックし再計算するか決める
    tx.serialize()
    need_gas_amount = tx.getsize() + len(input_address) * 96 + additional_fee
    if 0 <= tx.gas_amount - need_gas_amount < 10000:
        # input/outputを混ぜる
        random.shuffle(tx.inputs)
        return input_address
    else:
        logging.debug("Retry calculate tx fee. [{}=>{}]".format(tx.gas_amount, need_gas_amount))
        tx.gas_amount = need_gas_amount
        return fill_inputs_outputs(tx=tx, unspents=unspents,
                                   chain_cur=chain_cur, fee_coin_id=fee_coin_id, additional_fee=additional_fee)


def randomize_output(tx, fee_coin_id):
    random.shuffle(tx.outputs)
    while tx.outputs[0][1] != fee_coin_id:
        random.shuffle(tx.outputs)


def replace_redeem_dummy_address(tx, account_cur):
    new_redeem_address = set()
    for index, (address, coin_id, amount) in enumerate(tx.outputs):
        if address != DUMMY_REDEEM_ADDRESS:
            continue
        sk, pk, new_address = new_keypair(group=C.ANT_UNKNOWN, cur=account_cur)
        tx.outputs[index] = (new_address, coin_id, amount)
        new_redeem_address.add(new_address)
    tx.serialize()
    return new_redeem_address


def recode_account_movement(tx, new_redeem_address, from_group, chain_cur, account_cur):
    input_index = 0
    for txhash, txindex in tx.inputs:
        address, coin_id, amount = read_tx_output(txhash=txhash, txindex=txindex, cur=chain_cur)
        move_account_balance(from_group=from_group, to_group=C.ANT_OUTSIDE, coins=CoinObject(coin_id, amount),
                             cur=account_cur, txhash=tx.hash, direction=1, txindex=input_index, f_allow_minus=True)
        input_index += 1
    output_index = 0
    for address, coin_id, amount in tx.outputs:
        if address in new_redeem_address:
            to_group = from_group
        else:
            to_group = address2group(address=address, cur=account_cur)
            to_group = to_group if to_group else C.ANT_OUTSIDE
        move_account_balance(from_group=C.ANT_OUTSIDE, to_group=to_group, coins=CoinObject(coin_id, amount),
                             cur=account_cur, txhash=tx.hash, direction=0, txindex=output_index, f_allow_minus=True)
        output_index += 1


def setup_signature(tx, input_address):
    # tx.signature.clear()
    for address in input_address:
        sign_pairs = message2signature(raw=tx.b, address=address)
        tx.signature.append(sign_pairs)


__all__ = [
    "DUMMY_REDEEM_ADDRESS",
    "fill_inputs_outputs",
    "randomize_output",
    "replace_redeem_dummy_address",
    "recode_account_movement",
    "setup_signature"
]
