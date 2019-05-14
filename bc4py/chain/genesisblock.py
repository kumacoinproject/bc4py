from bc4py.chain.difficulty import MAX_BITS
from bc4py.config import C, V, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from time import time
import msgpack
from more_itertools import chunked


def create_genesis_block(mining_supply,
                         block_span,
                         hrp='pycon',
                         digit_number=8,
                         minimum_price=100,
                         consensus=None,
                         genesis_msg="blockchain for python",
                         premine=None):
    """
    Height0のGenesisBlockを作成する
    :param mining_supply: PoW/POS合わせた全採掘量、プリマインを除く
    :param block_span: Blockの採掘間隔(Sec)
    :param hrp: human readable part
    :param digit_number: コインの分解能
    :param minimum_price: 最小gas_price
    :param consensus: 採掘アルゴ {consensus: ratio(0~100), ..}
    :param genesis_msg: GenesisMessage
    :param premine: プリマイン [(address, coin_id, amount), ...]
    """

    # default: Yescript9割, Stake1割の分配
    consensus = consensus or {C.BLOCK_X16S_POW: 100}
    if sum(consensus.values()) != 100:
        raise BlockChainError('sum of consensus values is 100 [!={}]'.format(sum(consensus.values())))
    elif not isinstance(sum(consensus.values()), int):
        raise BlockChainError('value is int only.')
    elif not (0 < min(consensus.values()) <= 100):
        raise BlockChainError('out of range {}'.format(min(consensus.values())))
    elif not (0 < max(consensus.values()) <= 100):
        raise BlockChainError('out of range {}'.format(min(consensus.values())))
    all_consensus = {
        C.BLOCK_COIN_POS, C.BLOCK_CAP_POS, C.BLOCK_FLK_POS, C.BLOCK_YES_POW, C.BLOCK_X11_POW, C.BLOCK_HMQ_POW,
        C.BLOCK_LTC_POW, C.BLOCK_X16S_POW
    }
    if len(set(consensus.keys()) - all_consensus) > 0:
        raise BlockChainError('Not found all_consensus number {}'.format(set(consensus.keys()) - all_consensus))
    elif len(set(consensus.keys()) & all_consensus) == 0:
        raise BlockChainError('No usable consensus found {}'.format(set(consensus.keys()) & all_consensus))
    elif not (0 < len(hrp) < 5):
        raise BlockChainError('hrp is too long hrp={}'.format(hrp))
    elif 'dummy' in hrp or '1' in hrp:
        raise BlockChainError('Not allowed  include "dummy" and "1" str {}'.format(hrp))

    # params
    assert isinstance(minimum_price, int), 'minimum_price is INT'
    genesis_time = int(time())
    # BLockChainの設定TX
    params = {
        'hrp': hrp,
        'genesis_time': genesis_time,  # GenesisBlockの採掘時間
        'mining_supply': mining_supply,  # 全採掘量
        'block_span': block_span,  # ブロックの採掘間隔
        'digit_number': digit_number,  # 小数点以下の桁数
        'minimum_price': minimum_price,
        'contract_minimum_amount': pow(10, digit_number),
        'consensus': consensus,  # Block承認のアルゴリズム
    }
    V.BLOCK_GENESIS_TIME = genesis_time
    # first tx
    first_tx = TX.from_dict(
        tx={
            'type': C.TX_GENESIS,
            'time': 0,
            'deadline': 10800,
            'gas_price': 0,
            'gas_amount': 0,
            'message_type': C.MSG_PLAIN,
            'message': genesis_msg.encode()
        })
    first_tx.height = 0
    # premine
    premine_txs = list()
    for index, chunk in enumerate(chunked(premine or list(), 255)):
        tx = TX.from_dict(tx={
            'type': C.TX_TRANSFER,
            'time': 0,
            'deadline': 10800,
            'outputs': chunk,
            'gas_price': 0,
            'gas_amount': 0
        })
        tx.height = 0
        premine_txs.append(tx)
    # height0のBlock生成
    genesis_block = Block.from_dict(block={
        'merkleroot': b'\x00' * 32,
        'time': 0,
        'previous_hash': b'\xff' * 32,
        'bits': MAX_BITS,
        'nonce': b'\xff' * 4
    })
    # block params
    genesis_block.height = 0
    genesis_block.flag = C.BLOCK_GENESIS
    # block body
    genesis_block.txs.append(first_tx)
    genesis_block.txs.extend(premine_txs)
    genesis_block.bits2target()
    genesis_block.target2diff()
    genesis_block.update_merkleroot()
    genesis_block.serialize()
    return genesis_block, params
