from bc4py import __chain_version__
from bc4py.config import C, P, BlockChainError
from bc4py.chain.tx import TX
from bc4py.chain.utils import check_output_format
from bc4py.user import CoinObject
from bc4py.contract.emulate import try_emulate
from bc4py.database.account import create_new_user_keypair
from bc4py.database.tools import get_contract_storage, get_usedindex, get_utxo_iter
import bjson
import logging

"""
TX_CREATE_CONTRACT
c_address, c_bin, c_cs

TX_START_CONTRACT
c_address, c_method, c_args, c_redeem

TX_FINISH_CONTRACT
c_result, start_hash, cs_diff
"""

DUMMY_REDEEM_ADDRESS = '_____DUMMY______REDEEM______ADDRESS_____'  # 40letters


def failed_finish_tx(start_tx):
    message = bjson.dumps((False, start_tx.hash, None), compress=False)
    return TX(tx={
        'version': __chain_version__,
        'type': C.TX_FINISH_CONTRACT,
        'time': start_tx.time,
        'deadline': start_tx.deadline,
        'inputs': list(),
        'outputs': list(),
        'gas_price': start_tx.gas_price,
        'gas_amount': 0,
        'message_type': C.MSG_BYTE,
        'message': message})


def finish_contract_tx(start_tx, f_limit=True):
    assert start_tx.height is None, 'StartTX height is None.'
    assert P.VALIDATOR_OBJ, 'You are not a validator.'
    c_address, c_data, c_args, c_redeem = bjson.loads(start_tx.message)
    if f_limit:
        gas_limit = start_tx.gas_amount - start_tx.getsize()
    else:
        gas_limit = None
    status, result, estimate_gas, line = try_emulate(start_tx, gas_limit)
    if status:
        # 成功時
        outputs, cs_result = result
        if cs_result is None:
            message = bjson.dumps((True, start_tx.hash, None), compress=False)
        else:
            cs = get_contract_storage(c_address)
            cs_diff = cs.diff_dev(new_key_value=cs_result.key_value)
            message = bjson.dumps((True, start_tx.hash, cs_diff), compress=False)
        try:
            check_output_format(outputs)
        except BlockChainError as e:
            logging.debug("Contract failed `emulate success` {}".format(e))
            return failed_finish_tx(start_tx), estimate_gas

    else:
        # 失敗時
        outputs = None
        logging.debug("Contract failed `emulate failed` {}".format(result))
        return failed_finish_tx(start_tx), 0
    # finish tx 作成
    finish_tx = TX(tx={
        'version': __chain_version__,
        'type': C.TX_FINISH_CONTRACT,
        'time': start_tx.time,
        'deadline': start_tx.deadline,
        'inputs': list(),
        'outputs': outputs or list(),
        'gas_price': start_tx.gas_price,
        'gas_amount': 1,
        'message_type': C.MSG_BYTE,
        'message': message})
    to_user_redeem = (c_redeem, 0, 0)
    finish_tx.outputs.append(to_user_redeem)  # gas_amountを返す
    # fill input/output
    # TODO: c_redeemを用いてFeeを還元
    redeem_gas = start_tx.gas_amount - start_tx.getsize() - estimate_gas
    if not fill_inputs_outputs(finish_tx, c_address, start_tx.hash, redeem_gas):
        return failed_finish_tx(start_tx), estimate_gas
    redeem_idx = finish_tx.outputs.index(to_user_redeem)
    redeem_amount = -1 * finish_tx.gas_amount * finish_tx.gas_price
    finish_tx.outputs[redeem_idx] = (c_redeem, 0, redeem_amount)
    replace_redeem_dummy_address(finish_tx, c_address)
    finish_tx.serialize()
    return finish_tx, estimate_gas


def fill_inputs_outputs(finish_tx, c_address, start_hash, redeem_gas, dust_percent=0.8):
    assert finish_tx.gas_price > 0, "Gas params is none zero."
    # outputsの合計を取得
    output_coins = CoinObject()
    for address, coin_id, amount in finish_tx.outputs.copy():
        if address == DUMMY_REDEEM_ADDRESS:
            # 償還Outputは再構築するので消す
            finish_tx.outputs.remove((address, coin_id, amount))
            continue
        output_coins[coin_id] += amount
    # 一時的にfeeの概算
    fee_coins = CoinObject(coin_id=0, amount=finish_tx.gas_price * finish_tx.gas_amount)
    # 必要なだけinputsを取得
    finish_tx.inputs.clear()
    need_coins = output_coins + fee_coins
    input_coins = CoinObject()
    f_dust_skipped = False
    for dummy, height, txhash, txindex, coin_id, amount in get_utxo_iter({c_address}):
        if coin_id not in need_coins:
            continue
        elif need_coins[coin_id] * dust_percent > amount:
            f_dust_skipped = True
            continue
        need_coins[coin_id] -= amount
        input_coins[coin_id] += amount
        finish_tx.inputs.append((txhash, txindex))
        if need_coins.is_all_minus_amount():
            break
    else:
        if f_dust_skipped and dust_percent > 0.1:
            new_dust_percent = round(dust_percent * 0.8, 4)
            logging.debug("Retry by lower dust percent. {}=>{}".format(dust_percent, new_dust_percent))
            return fill_inputs_outputs(finish_tx, c_address, start_hash, redeem_gas, new_dust_percent)
        # 失敗に変更
        logging.debug('Insufficient balance. inputs={} needs={}'.format(input_coins, need_coins))
        return False
    # redeemを計算
    redeem_coins = input_coins - output_coins - fee_coins
    for coin_id, amount in redeem_coins:
        finish_tx.outputs.append((DUMMY_REDEEM_ADDRESS, coin_id, amount))
    # Feeをチェックし再計算するか決める
    finish_tx.serialize()
    need_gas_amount = finish_tx.getsize() - redeem_gas
    if finish_tx.gas_amount == need_gas_amount:
        return True
    elif need_gas_amount > 0:
        # FINISH_TXのみGasは負の値
        # Gas使いすぎ,失敗に変更
        logging.debug('Too match gas used. need_gas={}'.format(need_gas_amount))
        return False
    else:
        # insufficient gas
        logging.debug("Retry calculate tx fee. [{}=>{}+{}={}]".format(
            finish_tx.gas_amount, finish_tx.getsize(), redeem_gas, need_gas_amount))
        finish_tx.gas_amount = need_gas_amount
        return fill_inputs_outputs(finish_tx, c_address, start_hash, redeem_gas, dust_percent)


def replace_redeem_dummy_address(tx, c_address):
    for index, (address, coin_id, amount) in enumerate(tx.outputs):
        if address != DUMMY_REDEEM_ADDRESS:
            continue
        tx.outputs[index] = (c_address, coin_id, amount)
    tx.serialize()
