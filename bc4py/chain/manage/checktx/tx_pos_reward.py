from bc4py.config import C, BlockChainError
from bc4py.chain.utils import GompertzCurve
from bc4py.chain.difficulty import get_pos_bias_by_hash
from bc4py.database.chain.read import read_tx_output, read_tx_object


def check_tx_pos_reward(tx, include_block, cur):
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
    base_tx = read_tx_object(txhash=txhash, cur=cur)
    input_address, input_coin_id, input_amount = read_tx_output(txhash=txhash, txindex=txindex, cur=cur)
    output_address, output_coin_id, output_amount = tx.outputs[0]
    reward = GompertzCurve.calc_block_reward(tx.height)
    pos_bias = get_pos_bias_by_hash(previous_hash=include_block.previous_hash)[0]
    include_block.bits2target()

    if input_address != output_address:
        raise BlockChainError('Input address differ from output address.')
    elif not (input_coin_id == output_coin_id == 0):
        raise BlockChainError('Input and output coinID is zero.')
    elif input_amount + reward != output_amount:
        raise BlockChainError('Inout amount wrong [{}+{}={}]'.format(input_amount, reward, output_amount))
    elif tx.version != 1 or tx.message_type != C.MSG_NONE:
        raise BlockChainError('Not correct tx version or msg_type.')
    elif not (tx.height > base_tx.height + C.MATURE_HEIGHT):
        raise BlockChainError('Source TX height is too young. [{}>{}+{}]'
                              .format(tx.height, base_tx.height, C.MATURE_HEIGHT))
    elif not (include_block.time == tx.time == tx.deadline - 10800):
        raise BlockChainError('TX time is wrong 1. [{}={}={}-10800]'.format(include_block.time, tx.time, tx.deadline))
    elif not tx.pos_check(include_block.previous_hash, pos_bias, include_block.target_hash):
        raise BlockChainError('Proof of stake check is failed.')
