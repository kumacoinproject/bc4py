#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py import __chain_version__
from bc4py.chain.difficulty import MAX_BITS, MIN_BIAS_BITS
from bc4py.config import C, V, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.database.create import closing, create_db
from bc4py.database.account import create_new_user_keypair
from bc4py.contract.tools import contract2binary
from bc4py.contract.c_validator import Contract
from nem_ed25519.key import convert_address
import time
import logging
import bjson
from more_itertools import chunked


def create_genesis_block(all_supply, block_span, prefix=b'\x98', contract_prefix=b'\x12',
                         digit_number=8, minimum_price=100, consensus=C.BLOCK_POW,
                         pow_ratio=100, premine=None):
    """
    Height0のGenesisBlockを作成する
    :param all_supply: PoW/POS合わせた全採掘量、プリマインを除く
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
    assert isinstance(minimum_price, int), 'minimum_price is INT'
    genesis_time = int(time.time())
    # premine
    premine_txs = list()
    for index, chunk in enumerate(chunked(premine or list(), 256)):
        tx = TX(tx={
            'version': __chain_version__,
            'type': C.TX_TRANSFER,
            'time': 0,
            'deadline': 10800,
            'inputs': list(),
            'outputs': chunk,
            'gas_price': 0,
            'gas_amount': 0,
            'message_type': C.MSG_PLAIN,
            'message': 'Premine {}'.format(index).encode()})
        tx.height = 0
        premine_txs.append(tx)
    # validator
    V.BLOCK_GENESIS_TIME = int(time.time())
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        ck = create_new_user_keypair(C.ANT_CONTRACT, db.cursor())
        db.commit()
    c_address = convert_address(ck, contract_prefix)
    c_bin = contract2binary(Contract)
    c_cs = {
        ck.encode(): b'\x00\x00\x00\x00',
        b'\x00'+b'\x00\x00\x00\x00': b'\x01'
    }  # TODO:　初期値どうする？
    validator_tx = TX(tx={
            'version': __chain_version__,
            'type': C.TX_CREATE_CONTRACT,
            'time': 0,
            'deadline': 10800,
            'inputs': list(),
            'outputs': list(),
            'gas_price': 0,
            'gas_amount': 0,
            'message_type': C.MSG_BYTE,
            'message': bjson.dumps((c_address, c_bin, c_cs), compress=False)})
    validator_tx.height = 0
    params = {
        'prefix': prefix,  # CompressedKey prefix
        'contract_prefix': contract_prefix,  # ContractKey prefix
        'validator_address': c_address,
        'genesis_time': genesis_time,  # GenesisBlockの採掘時間
        'all_supply': all_supply,  # 全採掘量
        'block_span': block_span,  # ブロックの採掘間隔
        'digit_number': digit_number,  # 小数点以下の桁数
        'minimum_price': minimum_price,
        'contract_minimum_amount': pow(10, digit_number),
        'consensus': consensus,  # Block承認のアルゴリズム
        'pow_ratio': pow_ratio}  # POWによるBlock採掘割合
    # BLockChainの設定TX
    setting_tx = TX(tx={
        'version': __chain_version__,
        'type': C.TX_GENESIS,
        'time': 0,
        'deadline': 10800,
        'inputs': list(),
        'outputs': list(),
        'gas_price': 0,
        'gas_amount': 0,
        'message_type': C.MSG_BYTE,
        'message': bjson.dumps(params, compress=False)})
    setting_tx.height = 0
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
    genesis_block.txs.append(setting_tx)
    genesis_block.txs.append(validator_tx)
    genesis_block.txs.extend(premine_txs)
    genesis_block.bits2target()
    genesis_block.target2diff()
    genesis_block.update_merkleroot()
    genesis_block.serialize()
    return genesis_block
