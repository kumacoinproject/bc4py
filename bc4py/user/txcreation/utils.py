from bc4py.user.utils import message2signature
from bc4py.config import C, BlockChainError
from bc4py.database.builder import builder, tx_builder, user_account
from bc4py.database.account import read_pooled_address_iter, create_new_user_keypair
from bc4py.user import CoinObject
import logging


DUMMY_REDEEM_ADDRESS = '_____DUMMY______REDEEM______ADDRESS_____'  # 40letters


def fill_inputs_outputs(tx, cur, fee_coin_id=0, additional_fee=0):
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
    fee_coins = CoinObject(coin_id=fee_coin_id, amount=tx.gas_price * tx.gas_amount)
    # 必要なだけinputsを取得
    tx.inputs.clear()
    need_coins = output_coins + fee_coins
    input_coins = CoinObject()
    input_address = set()
    for uuid, address, dummy in read_pooled_address_iter(cur):
        for dummy, txhash, txindex, coin_id, amount, f_used in builder.db.read_address_idx_iter(address):
            if f_used:
                continue
            elif txindex in tx_builder.get_usedindex(txhash):
                continue
            need_coins[coin_id] -= amount
            input_coins[coin_id] += amount
            input_address.add(address)
            tx.inputs.append((txhash, txindex))
            if need_coins.is_all_minus_amount():
                break
        if need_coins.is_all_minus_amount():
            break
    else:
        raise BlockChainError('Insufficient balance. inputs={} needs={}'.format(input_coins, need_coins))
    # redeemを計算
    redeem_coins = input_coins - output_coins - fee_coins
    for coin_id, amount in redeem_coins:
        tx.outputs.append((DUMMY_REDEEM_ADDRESS, coin_id, amount))
    # Feeをチェックし再計算するか決める
    tx.serialize()
    need_gas_amount = tx.getsize() + len(input_address) * 96 + additional_fee
    if 0 <= tx.gas_amount - need_gas_amount < 10000:
        # input/outputを混ぜる
        return input_address
    else:
        # insufficient gas
        logging.debug("Retry calculate tx fee. [{}=>{}+{}={}]".format(
            tx.gas_amount, tx.getsize()+len(input_address) * 96, additional_fee, need_gas_amount))
        tx.gas_amount = need_gas_amount
        return fill_inputs_outputs(tx, cur, fee_coin_id, additional_fee)


def replace_redeem_dummy_address(tx, cur):
    new_redeem_address = set()
    for index, (address, coin_id, amount) in enumerate(tx.outputs):
        if address != DUMMY_REDEEM_ADDRESS:
            continue
        new_address = create_new_user_keypair(C.ANT_NAME_UNKNOWN, cur)
        tx.outputs[index] = (new_address, coin_id, amount)
        new_redeem_address.add(new_address)
    tx.serialize()
    return new_redeem_address


def setup_signature(tx, input_address):
    # tx.signature.clear()
    for address in input_address:
        sign_pairs = message2signature(raw=tx.b, address=address)
        tx.signature.append(sign_pairs)


def check_enough_amount(sender, send_coins, fee_coins):
    from_coins = user_account.get_balance()[sender]
    remain_coins = from_coins - send_coins - fee_coins
    if not remain_coins.is_all_plus_amount():
        raise BlockChainError('Not enough balance in id={} {}.'.format(sender, from_coins))


__all__ = [
    "DUMMY_REDEEM_ADDRESS",
    "fill_inputs_outputs",
    "replace_redeem_dummy_address",
    "setup_signature",
    "check_enough_amount"
]
