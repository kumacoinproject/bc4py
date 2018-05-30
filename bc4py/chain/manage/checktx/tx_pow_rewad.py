from bc4py.config import BlockChainError
from bc4py.chain.utils import GompertzCurve


def check_tx_pow_reward(tx, include_block):
    if not (len(tx.inputs) == 0 and len(tx.outputs) == 1):
        raise BlockChainError('Inout is 0, output is 1 len.')
    elif include_block.txs.index(tx) != 0:
        raise BlockChainError('Proof tx is index 0.')
    elif not (tx.gas_price == 0 and tx.gas_amount == 0):
        raise BlockChainError('Pow gas info is wrong. [{}, {}]'.format(tx.gas_price, tx.gas_amount))
    elif len(tx.message) > 96:
        raise BlockChainError('Pow msg is less than 96bytes. [{}b>96b]'.format(len(tx.message)))

    address, coin_id, amount = tx.outputs[0]
    reward = GompertzCurve.calc_block_reward(tx.height)
    fees = sum(tx.gas_amount * tx.gas_price for tx in include_block.txs)

    if not (include_block.time == tx.time == tx.deadline - 10800):
        raise BlockChainError('TX time is wrong 3. [{}={}={}-10800]'.format(include_block.time, tx.time, tx.deadline))
    elif not (coin_id == 0 and amount <= reward + fees):
        raise BlockChainError('Input and output is wrong {} [{}<={}+{}]'.format(coin_id, amount, reward, fees))
    elif not include_block.pow_check():
        include_block.work2diff()
        include_block.target2diff()
        print(include_block.getinfo())
        raise BlockChainError('Proof of work check is failed. [{}<{}]'
                              .format(include_block.difficulty, include_block.work_difficulty))
