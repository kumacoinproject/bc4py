from bc4py import __chain_version__
from bc4py.config import C, BlockChainError
from bc4py_extension import poc_hash, poc_work, scope_index
from bc4py.chain.utils import GompertzCurve
from bc4py.database.builder import tx_builder
from nem_ed25519.signature import verify


def check_tx_pow_reward(tx, include_block):
    if not (len(tx.inputs) == 0 and len(tx.outputs) == 1):
        raise BlockChainError('Inout is 0, output is 1 len.')
    elif include_block.txs.index(tx) != 0:
        raise BlockChainError('Proof tx is index 0.')
    elif not (tx.gas_price == 0 and tx.gas_amount == 0):
        raise BlockChainError('Pow gas info is wrong. [{}, {}]'.format(tx.gas_price, tx.gas_amount))
    elif len(tx.message) > 96:
        raise BlockChainError('Pow msg is less than 96bytes. [{}b>96b]'.format(len(tx.message)))
    elif len(tx.signature) != 0:
        raise BlockChainError('signature is only zero not {}'.format(len(tx.signature)))

    address, coin_id, amount = tx.outputs[0]
    reward = GompertzCurve.calc_block_reward(include_block.height)
    fees = sum(tx.gas_amount * tx.gas_price for tx in include_block.txs)

    if not (include_block.time == tx.time == tx.deadline - 10800):
        raise BlockChainError('TX time is wrong 3. [{}={}={}-10800]'.format(include_block.time, tx.time, tx.deadline))
    elif not (coin_id == 0 and amount <= reward + fees):
        raise BlockChainError('Input and output is wrong coin={} [{}<={}+{}]'.format(coin_id, amount, reward, fees))
    elif not include_block.pow_check():
        include_block.work2diff()
        include_block.target2diff()
        print(include_block.getinfo())
        raise BlockChainError('Proof of work check is failed. [{}<{}]'
                              .format(include_block.difficulty, include_block.work_difficulty))


def check_tx_pos_reward(tx, include_block):
    # POS報酬TXの検査
    if not (len(tx.inputs) == len(tx.outputs) == 1):
        raise BlockChainError('Inputs and outputs is only 1 len.')
    elif include_block.txs.index(tx) != 0:
        raise BlockChainError('Proof tx is index 0.')
    elif not (tx.gas_price == 0 and tx.gas_amount == 0):
        raise BlockChainError('Pos gas info is wrong. [{}, {}]'.format(tx.gas_price, tx.gas_amount))
    elif not (tx.message_type == C.MSG_NONE and tx.message == b''):
        raise BlockChainError('Pos msg is None type. [{},{}]'.format(tx.message_type, tx.message))

    txhash, txindex = tx.inputs[0]
    base_tx = tx_builder.get_tx(txhash)
    if base_tx is None:
        print(list(tx_builder.chained_tx.values()))
        raise BlockChainError('Not found PosBaseTX:{} of {}.'.format(txhash.hex(), tx))
    input_address, input_coin_id, input_amount = base_tx.outputs[txindex]
    tx.pos_amount = input_amount
    output_address, output_coin_id, output_amount = tx.outputs[0]
    reward = GompertzCurve.calc_block_reward(include_block.height)
    include_block.bits2target()

    if input_address != output_address:
        raise BlockChainError('Input address differ from output address. [{}!={}]'.format(input_address, output_address))
    elif not (input_coin_id == output_coin_id == 0):
        raise BlockChainError('Input and output coinID is zero.')
    elif input_amount + reward != output_amount:
        raise BlockChainError('Inout amount wrong [{}+{}!={}]'.format(input_amount, reward, output_amount))
    elif tx.version != __chain_version__ or tx.message_type != C.MSG_NONE:
        raise BlockChainError('Not correct tx version or msg_type.')
    elif base_tx.height is None:
        raise BlockChainError('Source TX is unconfirmed. {}'.format(base_tx))
    elif not (include_block.height > base_tx.height + C.MATURE_HEIGHT):
        raise BlockChainError('Source TX height is too young. [{}>{}+{}]'
                              .format(include_block.height, base_tx.height, C.MATURE_HEIGHT))
    elif not (include_block.time == tx.time == tx.deadline - 10800):
        raise BlockChainError('TX time is wrong 1. [{}={}={}-10800]'.format(include_block.time, tx.time, tx.deadline))
    elif not tx.pos_check(include_block.previous_hash, include_block.target_hash):
        raise BlockChainError('Proof of stake check is failed.')


def check_tx_poc_reward(tx, include_block):
    if not (len(tx.inputs) == 0 and len(tx.outputs) == 1):
        raise BlockChainError('inputs is 0 and outputs is 1')
    elif include_block.txs.index(tx) != 0:
        raise BlockChainError('Proof tx is index 0.')
    elif not (tx.gas_price == 0 and tx.gas_amount == 0):
        raise BlockChainError('PoC gas info is wrong. [{}, {}]'.format(tx.gas_price, tx.gas_amount))
    elif not (tx.message_type == C.MSG_NONE and tx.message == b''):
        raise BlockChainError('PoC msg is None type. [{},{}]'.format(tx.message_type, tx.message))
    elif len(tx.signature) != 1:
        raise BlockChainError('signature is only one not {}'.format(len(tx.signature)))

    o_address, o_coin_id, o_amount = tx.outputs[0]
    reward = GompertzCurve.calc_block_reward(include_block.height)
    total_fee = sum(tx.gas_price * tx.gas_amount for tx in include_block.txs)
    include_block.bits2target()

    if o_coin_id != 0:
        raise BlockChainError('output coinID is 0.')
    if reward + total_fee != o_amount:
        raise BlockChainError('Inout amount wrong [{}+{}!={}]'.format(reward, total_fee, o_amount))
    if tx.version != __chain_version__:
        raise BlockChainError('Not correct tx version')
    if not (include_block.time == tx.time == tx.deadline - 10800):
        raise BlockChainError('TX time is wrong 1. [{}={}={}-10800]'
                              .format(include_block.time, tx.time, tx.deadline))

    # work check
    scope_hash = poc_hash(address=o_address, nonce=include_block.nonce)
    index = scope_index(include_block.previous_hash)
    work_hash = poc_work(
        time=include_block.time,
        scope_hash=scope_hash[index*32:index*32+32],
        previous_hash=include_block.previous_hash)
    if int.from_bytes(work_hash, 'little') > int.from_bytes(include_block.target_hash, 'little'):
        raise BlockChainError('PoC check is failed, work={}'.format(work_hash.hex()))

    # signature check
    try:
        pk, sign = tx.signature[0]
        verify(msg=include_block.b, sign=sign, pk=pk)
    except Exception:
        raise BlockChainError('verification failed on PoC signature')


__all__ = [
    "check_tx_pow_reward",
    "check_tx_pos_reward",
    "check_tx_poc_reward",
]
