from bc4py import __chain_version__
from bc4py.config import C, BlockChainError
from bc4py_extension import poc_hash, poc_work, scope_index
from bc4py.chain.utils import GompertzCurve
from bc4py.chain.checking.utils import stake_coin_check, is_mature_input
from bc4py.database.tools import get_output_from_input


def check_tx_pow_reward(tx, include_block):
    if not (len(tx.inputs) == 0 and len(tx.outputs) > 0):
        raise BlockChainError('Inout is 0, output is more than 1')
    elif include_block.txs.index(tx) != 0:
        raise BlockChainError('Proof tx is index 0')
    elif not (tx.gas_price == 0 and tx.gas_amount == 0):
        raise BlockChainError('Pow gas info is wrong. [{}, {}]'.format(tx.gas_price, tx.gas_amount))
    elif len(tx.message) > 96:
        raise BlockChainError('Pow msg is less than 96bytes. [{}b>96b]'.format(len(tx.message)))
    elif len(tx.signature) != 0:
        raise BlockChainError('signature is only zero not {}'.format(len(tx.signature)))

    total_output_amount = 0
    for address, coin_id, amount in tx.outputs:
        if coin_id != 0:
            raise BlockChainError('Output coin_id is zero not {}'.format(coin_id))
        total_output_amount += amount
    # allow many outputs for PoW reward distribution
    extra_output_fee = (len(tx.outputs) - 1) * C.EXTRA_OUTPUT_REWARD_FEE
    reward = GompertzCurve.calc_block_reward(include_block.height)
    income_fee = sum(tx.gas_amount * tx.gas_price for tx in include_block.txs)

    if not (include_block.time == tx.time == tx.deadline - 10800):
        raise BlockChainError('TX time is wrong 3. [{}={}={}-10800]'.format(include_block.time, tx.time,
                                                                            tx.deadline))
    elif total_output_amount > reward + income_fee - extra_output_fee:
        raise BlockChainError('Input and output is wrong [{}<{}+{}-{}]'
                              .format(total_output_amount, reward, income_fee, extra_output_fee))


def check_tx_pos_reward(tx, include_block):
    # POS報酬TXの検査
    if not (len(tx.inputs) == len(tx.outputs) == 1):
        raise BlockChainError('Inputs and outputs is only 1 len')
    elif include_block.txs.index(tx) != 0:
        raise BlockChainError('Proof tx is index 0')
    elif include_block.version != 0:
        raise BlockChainError('pos block version is 0')
    elif not (tx.gas_price == 0 and tx.gas_amount == 0):
        raise BlockChainError('Pos gas info is wrong. [{}, {}]'.format(tx.gas_price, tx.gas_amount))
    elif not (tx.message_type == C.MSG_NONE and tx.message == b''):
        raise BlockChainError('Pos msg is None type. [{},{}]'.format(tx.message_type, tx.message))

    txhash, txindex = tx.inputs[0]
    if not is_mature_input(base_hash=txhash, limit_height=include_block.height - C.MATURE_HEIGHT):
        raise BlockChainError('Source is not mature, {} {}'.format(include_block.height, txhash.hex()))
    base_pair = get_output_from_input(txhash, txindex, best_block=include_block)
    if base_pair is None:
        raise BlockChainError('Not found PosBaseTX:{} of {}'.format(txhash.hex(), tx))
    input_address, input_coin_id, input_amount = base_pair
    tx.pos_amount = input_amount
    output_address, output_coin_id, output_amount = tx.outputs[0]
    reward = GompertzCurve.calc_block_reward(include_block.height)
    include_block.bits2target()

    if input_address != output_address:
        raise BlockChainError('Input address differ from output address. [{}!={}]'.format(
            input_address, output_address))
    elif not (input_coin_id == output_coin_id == 0):
        raise BlockChainError('Input and output coinID is zero')
    elif input_amount + reward != output_amount:
        raise BlockChainError('Inout amount wrong [{}+{}!={}]'.format(input_amount, reward, output_amount))
    elif tx.version != __chain_version__ or tx.message_type != C.MSG_NONE:
        raise BlockChainError('Not correct tx version or msg_type')
    elif not (include_block.time == tx.time == tx.deadline - 10800):
        raise BlockChainError('TX time is wrong 1. [{}={}={}-10800]'.format(include_block.time, tx.time,
                                                                            tx.deadline))
    elif not stake_coin_check(
            tx=tx, previous_hash=include_block.previous_hash, target_hash=include_block.target_hash):
        raise BlockChainError('Proof of stake check is failed')


def check_tx_poc_reward(tx, include_block):
    if not (len(tx.inputs) == 0 and len(tx.outputs) == 1):
        raise BlockChainError('inputs is 0 and outputs is 1')
    elif include_block.txs.index(tx) != 0:
        raise BlockChainError('Proof tx is index 0')
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
        raise BlockChainError('output coinID is 0')
    if reward + total_fee != o_amount:
        raise BlockChainError('Inout amount wrong [{}+{}!={}]'.format(reward, total_fee, o_amount))
    if tx.version != __chain_version__:
        raise BlockChainError('Not correct tx version')
    if not (include_block.time == tx.time == tx.deadline - 10800):
        raise BlockChainError('TX time is wrong 1. [{}={}={}-10800]'.format(include_block.time, tx.time,
                                                                            tx.deadline))

    # work check
    scope_hash = poc_hash(address=o_address, nonce=include_block.nonce)
    index = scope_index(include_block.previous_hash)
    work_hash = poc_work(
        time=include_block.time,
        scope_hash=scope_hash[index * 32:index*32 + 32],
        previous_hash=include_block.previous_hash)
    if int.from_bytes(work_hash, 'little') > int.from_bytes(include_block.target_hash, 'little'):
        raise BlockChainError('PoC check is failed, work={} target={}'.format(work_hash.hex(),
                                                                              include_block.target_hash.hex()))

    # signature check
    signed_cks = set(tx.verified_list)
    if len(signed_cks) != 1:
        raise BlockChainError('PoC signature num is wrong num={}'.format(len(signed_cks)))
    ck = signed_cks.pop()
    if ck != o_address:
        raise BlockChainError('PoC signature ck is miss math {}!={}'.format(ck, o_address))


__all__ = [
    "check_tx_pow_reward",
    "check_tx_pos_reward",
    "check_tx_poc_reward",
]
