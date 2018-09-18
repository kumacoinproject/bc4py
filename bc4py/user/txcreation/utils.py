from bc4py.user.utils import message2signature
from bc4py.config import C, BlockChainError
from bc4py.database.builder import user_account
from bc4py.database.account import create_new_user_keypair
from bc4py.database.tools import get_unspents_iter
from bc4py.user import CoinObject
import logging


DUMMY_REDEEM_ADDRESS = '_____DUMMY______REDEEM______ADDRESS_____'  # 40letters


def fill_inputs_outputs(tx, cur, fee_coin_id=0, additional_fee=0, dust_percent=0.8, utxo_cashe=None):
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
    f_dust_skipped = False
    if utxo_cashe is None:
        utxo_iter = get_unspents_iter(cur)
        utxo_cashe = list()
        f_put_cashe = True
    else:
        utxo_iter = utxo_cashe
        f_put_cashe = False
    for address, height, txhash, txindex, coin_id, amount in utxo_iter:
        if f_put_cashe:
            utxo_cashe.append((address, height, txhash, txindex, coin_id, amount))
        if coin_id not in need_coins:
            continue
        elif need_coins[coin_id] * dust_percent > amount:
            f_dust_skipped = True
            continue
        need_coins[coin_id] -= amount
        input_coins[coin_id] += amount
        input_address.add(address)
        tx.inputs.append((txhash, txindex))
        if need_coins.is_all_minus_amount():
            break
    else:
        if f_dust_skipped and dust_percent > 0.00001:
            new_dust_percent = round(dust_percent * 0.7, 6)
            logging.debug("Retry by lower dust percent. {}=>{}".format(dust_percent, new_dust_percent))
            return fill_inputs_outputs(tx, cur, fee_coin_id, additional_fee, new_dust_percent, utxo_cashe)
        elif len(tx.inputs) > 255:
            raise BlockChainError('Too many inputs, unspent tx\'s amount is too small.')
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
        return fill_inputs_outputs(tx, cur, fee_coin_id, additional_fee, dust_percent, utxo_cashe)


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
        raise BlockChainError('Not enough balance in id={} balance={} remains={}.'
                              .format(sender, from_coins, remain_coins))


__all__ = [
    "DUMMY_REDEEM_ADDRESS",
    "fill_inputs_outputs",
    "replace_redeem_dummy_address",
    "setup_signature",
    "check_enough_amount"
]
