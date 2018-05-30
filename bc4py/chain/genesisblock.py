#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.chain.difficulty import MAX_BITS, MIN_BIAS_BITS
from bc4py.database.create import create_db, closing
from bc4py.database.chain.write import recode_block, recode_tx
from bc4py.config import C, V, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
import time
import logging
import bjson
from binascii import hexlify


def create_genesis_block(all_supply, halving_span, block_span, prefix=b'\x98', contract_prefix=b'\x12',
                         digit_number=8, minimum_price=100, consensus=C.BLOCK_POW,
                         pow_ratio=100, premine=None):
    """
    Height0のGenesisBlockを作成する
    :param all_supply: PoW/POS合わせた全採掘量、プリマインを除く
    :param halving_span: 半減期(Sec)
    :param block_span: Blockの採掘間隔(Sec)
    :param prefix: 一般アドレスの頭文字、b'\x98'=N
    :param contract_prefix: コントラクトの頭文字、b'\x98'=C
    :param digit_number: コインの分解能
    :param minimum_price: 最小gas_price
    :param consensus: 採掘アルゴ、C.BLOCK_POS, C.BLOCK_POW, C.HYBRID の三つ
    :param pow_ratio: C.HYBRID指定時、POWで採掘するBlockの割合を100分率で
    :param premine: プリマイン [(address, coin_id, amount), ...]
    """
    if consensus == C.BLOCK_POS:
        assert premine is None, 'You need premine for POS'
        pow_ratio = 0
    elif consensus == C.BLOCK_POW:
        pow_ratio = 100
    elif consensus == C.HYBRID:
        assert 0 < pow_ratio < 100, 'need, 0 < ratio < 100'
    else:
        raise BlockChainError('not found consensus \"%s\"' % consensus)

    """params"""
    block_reward = round(all_supply / 2 / (halving_span // block_span))
    logging.info("BlockReward {}".format(block_reward / pow(10, digit_number)))
    assert block_reward > 0, 'block reward is minus.'
    assert isinstance(minimum_price, int), 'minimum_price is INT'
    genesis_time = int(time.time())
    params = {
        'prefix': prefix,  # CompressedKey prefix
        'contract_prefix': contract_prefix,  # ContractKey prefix
        'genesis_time': genesis_time,  # GenesisBlockの採掘時間
        'all_supply': all_supply,  # 全採掘量
        'halving_span': halving_span,  # ブロックの半減期の間隔
        'block_span': block_span,  # ブロックの採掘間隔
        'block_reward': block_reward,  # Blockの初期採掘報酬
        'digit_number': digit_number,  # 小数点以下の桁数
        'minimum_price': minimum_price,
        'consensus': consensus,  # Block承認のアルゴリズム
        'pow_ratio': pow_ratio}  # POWによるBlock採掘割合
    # BLockChainの設定TX
    setting_tx = TX(tx={
        'version': 1,
        'type': C.TX_GENESIS,
        'time': 0,
        'deadline': 10800,
        'inputs': list(),
        'outputs': list(),
        'gas_price': 0,
        'gas_amount': 0,
        'message_type': C.MSG_BYTE,
        'message': bjson.dumps(params)})
    setting_tx.height = 0
    genesis_txs = [setting_tx]
    if premine and len(premine) > 0:
        for i in range(len(premine) // 256 + 1):
            tx = TX(tx={
                'version': 1,
                'type': C.TX_GENESIS,
                'time': 0,
                'deadline': 10800,
                'inputs': list(),
                'outputs': premine[256*i:256*i+256],
                'gas_price': 0,
                'gas_amount': 0,
                'message_type': C.MSG_PLAIN,
                'message': 'Premine {}'.format(i).encode()})
            tx.height = 0
            genesis_txs.append(tx)
    # height0のBlock生成
    genesis_block = Block(block={
        'merkleroot': b'\x00'*32,
        'time': 0,
        'previous_hash': b'\xff'*32,
        'bits': MAX_BITS,
        'pos_bias': MIN_BIAS_BITS,
        'nonce': b'\xff'*4})
    # block params
    genesis_block.height = 0
    genesis_block.flag = C.BLOCK_GENESIS
    # block body
    genesis_block.txs = genesis_txs
    genesis_block.bits2target()
    genesis_block.target2diff()
    genesis_block.update_merkleroot()
    genesis_block.serialize()
    return genesis_block


def set_genesis_block(genesis_block):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        recode_block(genesis_block, cur=cur)
        for tx in genesis_block.txs:
            recode_tx(tx, cur=cur)
        db.commit()
    logging.info("Insert Genesis block {}".format(hexlify(genesis_block.hash).decode()))
