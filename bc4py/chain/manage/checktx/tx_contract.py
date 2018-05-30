from bc4py.config import C, V, BlockChainError
from bc4py.contract.finishtx import create_finish_tx
from bc4py.contract.exe import auto_emulate
from bc4py.contract.utils import binary2contract
from bc4py.database.chain.read import read_tx_output, read_contract_tx, read_contract_storage, max_block_height
from nem_ed25519.key import is_address
import bjson
import logging


def check_tx_create_contract(tx):
    if len(tx.inputs) == 0 or len(tx.outputs) == 0:
        raise BlockChainError('No inputs or outputs.')
    elif tx.message_type != C.MSG_BYTE:
        raise BlockChainError('create contract tx is bytes msg.')
    elif V.BLOCK_CONTRACT_PREFIX is None:
        raise BlockChainError('Not set contract prefix.')
    elif V.BLOCK_CONTRACT_PREFIX == V.BLOCK_PREFIX:
        raise BlockChainError('normal prefix same with contract prefix.')
    # GAS量チェック
    estimate_gas = tx.getsize() + C.CONTRACT_CREATE_FEE
    if estimate_gas > tx.gas_amount:
        raise BlockChainError('Insufficient gas [{}>{}]'.format(estimate_gas, tx.gas_amount))
    # Contractをデコードできるか
    c_address, c_bin = bjson.loads(tx.message)
    binary2contract(c_bin)
    if not is_address(c_address, V.BLOCK_CONTRACT_PREFIX):
        raise BlockChainError('Is not contract address. {}'.format(c_address))


def check_tx_start_contract(start_tx, include_block, cur):
    # Emulateの為に加えたHeightを加える
    if not include_block:
        old_height = start_tx.height
        start_tx.height = max_block_height(cur) + 1
    estimate_finish_tx, estimate_gas = create_finish_tx(start_tx=start_tx, cur=cur)
    gas_limit = start_tx.gas_amount - start_tx.getsize()
    gas_limit -= estimate_gas
    gas_limit -= estimate_finish_tx.getsize()
    logging.debug("Check gas info {}={}+{}+{}"
                  .format(start_tx.gas_amount, start_tx.getsize(), estimate_gas, estimate_finish_tx.getsize()))
    if gas_limit < 0:
        raise BlockChainError('run out of gas. {}'.format(gas_limit))
    estimate_status, start_hash, estimate_finish_diff = bjson.loads(estimate_finish_tx.message)

    if include_block:
        include_finish_tx, include_status, include_diff = find_finish_tx(include_block, start_tx)
        if include_status != estimate_status:
            # contract 不一致？
            raise BlockChainError('Do not match status [{}!={}]'.format(include_status, estimate_status))
        elif include_status:
            # contract 成功
            if include_diff != estimate_finish_diff:
                raise BlockChainError('Do not match diff [{}!={}]'.format(include_diff, estimate_finish_diff))
            # ここでOutputの検査をする
            c_address, c_data = bjson.loads(start_tx.message)
            compare_include2estimate_tx(include_finish_tx, estimate_finish_tx, c_address, cur)
        else:
            # contract 失敗
            if len(include_finish_tx.inputs) != 0:
                raise BlockChainError('Failed contract so inputs is zero. {}'.format(include_finish_tx.inputs))
            elif len(include_finish_tx.outputs) != 0:
                raise BlockChainError('Failed contract so outputs is zero. {}'.format(include_finish_tx.outputs))

    else:
        if not estimate_status:
            raise BlockChainError('Failed contract.')
    # Emulateの為に加えたHeightを戻す
    if not include_block:
        start_tx.height = old_height


def check_tx_finish_contract(finish_tx, include_block):
    if not include_block:
        raise BlockChainError('Cannot input block at finish tx.')
    elif finish_tx.gas_price != 0:
        raise BlockChainError('gas price is zero.')
    elif finish_tx.gas_amount != 0:
        raise BlockChainError('gas amount is zero.')
    elif finish_tx.message_type != C.MSG_BYTE:
        raise BlockChainError('message type is bytes.')
    # BlockにStartが含まれるか
    finish_status, start_hash, finish_diff = bjson.loads(finish_tx.message)
    for start_tx in include_block.txs:
        if start_tx.hash == start_hash:
            break
    else:
        raise BlockChainError('Cannot find start tx from {}.'.format(finish_tx))
    # 同一のStartTXの紐付けられている他のFinishTXが存在しないか
    for tx in include_block.txs:
        if tx.type != C.TX_FINISH_CONTRACT:
            continue
        elif tx.hash == finish_tx.hash:
            continue
        elif start_tx.hash == bjson.loads(tx.message)[1]:
            raise BlockChainError('Other finish tx found. {}'.format(tx))
    # BLock内のIndexはStartTX先、FinishTX後か
    if include_block.txs.index(start_tx) >= include_block.txs.index(finish_tx):
        raise BlockChainError('start tx index is higher than finish tx. [{}>={}]'
                              .format(include_block.txs.index(start_tx), include_block.txs.index(finish_tx)))


def find_finish_tx(include_block, start_tx):
    for finish_tx in include_block.txs:
        if finish_tx.type != C.TX_FINISH_CONTRACT:
            continue
        finish_status, start_hash, finish_diff = bjson.loads(finish_tx.message)
        if start_hash == start_tx.hash:
            return finish_tx, finish_status, finish_diff
    else:
        raise BlockChainError('Cannot find finish tx form {}.'.format(start_tx))


def compare_include2estimate_tx(include_tx, estimate_tx, c_address, cur):
    needs = list()
    # inputsが全てContractのUTXOか
    for txhash, txindex in include_tx.inputs:
        address, coin_id, amount = read_tx_output(txhash, txindex, cur)
        if address != c_address:
            raise BlockChainError('inputs of finish tx is contract utxo. [{}!={}]'
                                  .format(address, c_address))
    # outputsのContract先以外をincludeが全て含むか
    for address, coin_id, amount in estimate_tx.outputs:
        if address == c_address:
            continue
        needs.append((address, coin_id, amount))
    # Contractにより指定されたneedsを含むかチェック
    # それ以外のOutputsはContractに戻しているかチェック
    output_tmp = include_tx.outputs.copy()
    # 必要なOutputを除いてゆく
    used_coin_id = set()
    for o in needs:
        if len(o) != 3:
            raise BlockChainError('Outputs format is wrong.')
        elif not isinstance(o, tuple):
            raise BlockChainError('Output is tuple.')
        address, coin_id, amount = o
        if not isinstance(address, str) or len(address) != 40:
            raise BlockChainError('Not correct format address. {}'.format(address))
        elif not isinstance(coin_id, int) or not (0 <= coin_id):
            raise BlockChainError('Not correct format coin_id. {}'.format(coin_id))
        elif not isinstance(amount, int) or not (0 < amount):
            raise BlockChainError('Not correct format amount. {}'.format(amount))
        elif o not in output_tmp:
            raise BlockChainError('There is not output. {}'.format(o))
        output_tmp.remove(o)
        used_coin_id.add(coin_id)
    # Redeemのみ残っているかチェック
    if len(used_coin_id) < len(output_tmp):
        raise BlockChainError('Over limit outputs. [{}<{}]'.format(used_coin_id, output_tmp))
    # RedeemがContract先か
    for address, coin_id, amount in output_tmp:
        if address != c_address:
            raise BlockChainError('Redeem address is contract address. {}'.format(address))
        elif coin_id not in used_coin_id:
            raise BlockChainError('Not used coin_id in redeem. [{} not in {}]'.format(coin_id, used_coin_id))
        elif amount <= 0:
            raise BlockChainError('redeem amount is zero. {}'.format((address, coin_id, amount)))


__all__ = [
    "check_tx_create_contract",
    "check_tx_start_contract",
    "check_tx_finish_contract"
]
