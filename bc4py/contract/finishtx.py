from bc4py import __chain_version__
from bc4py.config import C, P, BlockChainError
from bc4py.chain.tx import TX
from bc4py.chain.utils import check_output_format
from bc4py.user import CoinObject
from bc4py.contract.exe import auto_emulate
from bc4py.database.builder import builder, tx_builder
from bc4py.database.account import create_new_user_keypair
from bc4py.database.tools import get_contract_binary, get_contract_storage
import bjson
import logging


DUMMY_REDEEM_ADDRESS = '_____DUMMY______REDEEM______ADDRESS_____'  # 40letters


def finish_contract_tx(start_tx, cur, set_limit=True):
    assert start_tx.height > 0, 'Need to set start tx height.'
    assert P.F_VALIDATOR, 'You are not a validator.'
    c_address, c_data, c_redeem = bjson.loads(start_tx.message)
    c_bin = get_contract_binary(c_address)
    if set_limit:
        gas_limit = start_tx.gas_amount - start_tx.getsize()
    else:
        gas_limit = None
    status, result, estimate_gas, line = auto_emulate(c_bin, c_address, start_tx, gas_limit)
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
            outputs = None
            message = bjson.dumps((False, start_tx.hash, None), compress=False)
            logging.debug("Contract failed `emulate success` {}".format(e))

    else:
        # 失敗時
        outputs = None
        message = bjson.dumps((False, start_tx.hash, None), compress=False)
        logging.debug("Contract failed `emulate failed` {}".format(result))
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
    redeem_gas = start_tx.gas_amount - (start_tx.getsize() + estimate_gas) // start_tx.gas_price
    fill_inputs_outputs(finish_tx, c_address, start_tx.hash, cur, redeem_gas)
    redeem_idx = finish_tx.outputs.index(to_user_redeem)
    finish_tx.outputs[redeem_idx] = (c_redeem, 0, -1 * finish_tx.gas_amount * finish_tx.gas_price)
    replace_redeem_dummy_address(finish_tx, cur)
    finish_tx.serialize()
    return finish_tx, estimate_gas


def fill_inputs_outputs(finish_tx, c_address, start_hash, cur, redeem_gas):
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
    for dummy, txhash, txindex, coin_id, amount, f_used in builder.db.read_address_idx_iter(c_address):
        if f_used:
            continue
        elif txindex in tx_builder.get_usedindex(txhash):
            continue
        need_coins[coin_id] -= amount
        input_coins[coin_id] += amount
        finish_tx.inputs.append((txhash, txindex))
        if need_coins.is_all_minus_amount():
            break
    else:
        # 失敗に変更
        finish_tx.inputs.clear()
        finish_tx.outputs.clear()
        finish_tx.gas_amount = 0
        finish_tx.message = bjson.dumps((False, start_hash, None), compress=False)
        logging.debug('Insufficient balance. inputs={} needs={}'.format(input_coins, need_coins))
        return
    # redeemを計算
    redeem_coins = input_coins - output_coins - fee_coins
    for coin_id, amount in redeem_coins:
        finish_tx.outputs.append((DUMMY_REDEEM_ADDRESS, coin_id, amount))
    # Feeをチェックし再計算するか決める
    finish_tx.serialize()
    need_gas_amount = finish_tx.getsize() - redeem_gas
    if finish_tx.gas_amount == need_gas_amount:
        return
    elif need_gas_amount > 0:
        # Gas使いすぎ,失敗に変更
        finish_tx.inputs.clear()
        finish_tx.outputs.clear()
        finish_tx.gas_amount = 0
        finish_tx.message = bjson.dumps((False, start_hash, None), compress=False)
        logging.debug('Too match gas used. need_gas={}'.format(need_gas_amount))
        return
    else:
        # insufficient gas
        logging.debug("Retry calculate tx fee. [{}=>{}+{}={}]".format(
            finish_tx.gas_amount, finish_tx.getsize(), redeem_gas, need_gas_amount))
        finish_tx.gas_amount = need_gas_amount
        fill_inputs_outputs(finish_tx, c_address, start_hash, cur, redeem_gas)
        return


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
