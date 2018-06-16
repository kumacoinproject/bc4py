from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.chain.tx import TX
from bc4py.user import CoinObject
from bc4py.contract.exe import auto_emulate
from bc4py.database.create import closing, create_db
from bc4py.database.chain.read import read_contract_tx, read_contract_storage, read_contract_utxo
from fasteners import InterProcessLock
import bjson
import logging
import os
import tempfile

finish_tx_cashe_lock = InterProcessLock(os.path.join(tempfile.gettempdir(), 'f.lock'))


def create_finish_tx_for_mining(unconfirmed, height):
    used_contract_address = set()
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        for tx in unconfirmed.copy():
            if tx.type == C.TX_FINISH_CONTRACT:
                unconfirmed.remove(tx)
            elif tx.type == C.TX_START_CONTRACT:
                try:
                    c_address, c_data = bjson.loads(tx.message)
                    # 1Blockに入るコントラクトアドレスは１つまで
                    if c_address in used_contract_address:
                        unconfirmed.remove(tx)
                        continue
                    with finish_tx_cashe_lock:
                        finish_tx = get_finish_tx_cashe(start_hash=tx.hash, height=height)
                        if not finish_tx:
                            tx.height = height
                            finish_tx, estimate_gas = create_finish_tx(start_tx=tx, cur=cur)
                            if tx.gas_amount < tx.getsize() + estimate_gas:
                                raise BlockChainError('exceed need gas amount. [{}<{}+{}]'
                                                      .format(tx.gas_amount, tx.getsize(), estimate_gas))
                            put_finish_tx_cashe(start_hash=tx.hash, height=height, finish_tx=finish_tx)
                            logging.debug("create!", finish_tx.getinfo())
                        else:
                            logging.debug("cashed..", height)
                        start_idx = unconfirmed.index(tx)
                        unconfirmed.insert(start_idx+1, finish_tx)
                        used_contract_address.add(c_address)
                except BlockChainError as e:
                    import traceback
                    traceback.print_exc()
                    unconfirmed.remove(tx)
                    logging.debug('finish tx creation failed {} "{}"'.format(tx, e))
            else:
                pass


def create_finish_tx(start_tx, cur, set_limit=True):
    assert start_tx.height > 0, 'Need to set start tx height.'
    c_address, c_data = bjson.loads(start_tx.message)
    contract_tx = read_contract_tx(c_address=c_address, cur=cur)
    if set_limit:
        gas_limit = start_tx.gas_amount - start_tx.getsize()
    else:
        gas_limit = None
    status, result, estimate_gas, line = auto_emulate(
        contract_tx=contract_tx, start_tx=start_tx, gas_limit=gas_limit)
    if status:
        # 成功時
        outputs, cs_result = result
        if cs_result is None:
            message = bjson.dumps((True, start_tx.hash, None), compress=False)
        else:
            cs = read_contract_storage(address=c_address, cur=cur, stop_hash=start_tx.hash)
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
        'gas_price': 0,
        'gas_amount': 0,
        'message_type': C.MSG_BYTE,
        'message': message})
    # inputs/outputsを補充
    output_coins = fill_finish_inout(c_address, start_tx, finish_tx, cur)
    # Redeemを設定
    output_coins.reverse_amount()
    for coin_id, amount in output_coins.items():
        finish_tx.outputs.append((c_address, coin_id, amount))
    finish_tx.serialize()
    return finish_tx, estimate_gas


def fill_finish_inout(c_address, start_tx, finish_tx, cur):
    output_coins = CoinObject()
    for address, coin_id, amount in finish_tx.outputs:
        output_coins[coin_id] += amount
    if output_coins.is_all_minus_amount():
        return output_coins
    for txhash, txindex, coin_id, amount in read_contract_utxo(c_address=c_address, cur=cur):
        if coin_id in output_coins and output_coins[coin_id] > 0:
            output_coins[coin_id] -= amount
            finish_tx.inputs.append((txhash, txindex))
        if output_coins.is_all_minus_amount():
            return output_coins
    # Balanceが足りない？StartTXのOutputsも使用してみる
    for txindex, (address, coin_id, amount) in enumerate(start_tx.outputs):
        if address != c_address:
            continue
        if coin_id in output_coins and output_coins[coin_id] > 0:
            output_coins[coin_id] -= amount
            finish_tx.inputs.append((start_tx.hash, txindex))
        if output_coins.is_all_minus_amount():
            return output_coins
    if not output_coins.is_all_minus_amount():
        # 失敗に変更
        finish_tx.inputs.clear()
        finish_tx.outputs.clear()
        finish_tx.message = bjson.dumps((False, start_tx.hash, None), compress=False)
        logging.debug("Contract success, but insufficient balance on contract. {}".format(output_coins))
        output_coins.coins.clear()
    return output_coins


def check_output_format(outputs):
    for o in outputs:
        if not isinstance(o, tuple):
            raise BlockChainError('Outputs is tuple.')
        elif len(o) != 3:
            raise BlockChainError('Output is three element.')
        address, coin_id, amount = o
        if not isinstance(address, str) or len(address) != 40:
            raise BlockChainError('output address is 40 string. {}'.format(address))
        elif not isinstance(coin_id, int) or coin_id < 0:
            raise BlockChainError('output coin_id is 0< int. {}'.format(coin_id))
        elif not isinstance(amount, int) or not(amount > 0):
            raise BlockChainError('output amount is 0<= int. {}'.format(amount))


# あくまで採掘時のキャッシュ代わりにするだけ
# get_finish_tx_cashe, put_finish_tx_cashe


def get_finish_tx_cashe(start_hash, height):
    with closing(create_db(V.DB_CASHE_PATH)) as db:
        cur = db.cursor()
        d = cur.execute("""
            SELECT `bin` FROM `finish_tx` WHERE `hash`=? AND `height`=?
            """, (start_hash, height)).fetchone()
        if d is None:
            return None
        finish_tx = TX(binary=d[0])
        finish_tx.height = height
        return finish_tx


def put_finish_tx_cashe(start_hash, height, finish_tx):
    with closing(create_db(V.DB_CASHE_PATH)) as db:
        cur = db.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO `finish_tx` VALUES (?,?,?)
            """, (start_hash, height, finish_tx.b))
        db.commit()
