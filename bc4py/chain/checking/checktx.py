from bc4py.config import C, V, BlockChainError
from bc4py.chain.checking.tx_reward import *
from bc4py.chain.checking.tx_mintcoin import *
from bc4py.chain.checking.tx_contract import *
from bc4py.chain.checking.utils import *
import logging
from binascii import hexlify
import time
from collections import deque


signature_cashe = deque([], maxlen=1000)


def check_tx(tx, include_block):
    # TXの正当性チェック
    f_amount_check = True
    f_signature_check = True
    f_size_check = True
    f_minimum_fee_check = True
    payfee_coin_id = 0

    # 共通検査
    if include_block:
        # tx is included block
        if tx not in include_block.txs:
            raise BlockChainError('Block not include the tx.')
        elif not (tx.time <= include_block.time <= tx.deadline):
            raise BlockChainError('block time isn\'t include in TX time-deadline. [{}<={}<={}]'
                                  .format(tx.time, include_block.time, tx.deadline))
        if 0 == include_block.txs.index(tx):
            if tx.type not in (C.TX_POS_REWARD, C.TX_POW_REWARD):
                raise BlockChainError('tx index is zero, but not proof tx.')
        elif tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
            raise BlockChainError('{} index is not 0 idx:{}.'
                                  .format(tx, include_block.txs.index(tx)))

    # 各々のタイプで検査
    if tx.type == C.TX_GENESIS:
        return

    elif tx.type == C.TX_POS_REWARD:
        f_amount_check = False
        f_minimum_fee_check = False
        check_tx_pos_reward(tx=tx, include_block=include_block)

    elif tx.type == C.TX_POW_REWARD:
        f_amount_check = False
        f_signature_check = False
        f_minimum_fee_check = False
        check_tx_pow_reward(tx=tx, include_block=include_block)

    elif tx.type == C.TX_TRANSFER:
        # feeに使用するCoinIDは0とは限らない
        payfee_coin_id = tx.outputs[0][1]
        if not (0 < len(tx.inputs) < 256 and 0 < len(tx.outputs) < 256):
            raise BlockChainError('Input and output is 1～256.')

    elif tx.type == C.TX_MINT_COIN:
        f_amount_check = False
        f_minimum_fee_check = False
        check_tx_mint_coin(tx=tx, include_block=include_block)

    elif tx.type == C.TX_CREATE_CONTRACT:
        f_minimum_fee_check = False
        check_tx_create_contract(tx=tx, include_block=include_block)

    elif tx.type == C.TX_START_CONTRACT:
        check_tx_start_contract(start_tx=tx, include_block=include_block)

    elif tx.type == C.TX_FINISH_CONTRACT:
        check_tx_finish_contract(finish_tx=tx, include_block=include_block)
        validator_check(tx, include_block)  # 必要十分な署名があるか

    else:
        raise BlockChainError('Unknown tx type "{}"'.format(tx.type))

    # Inputs origin チェック
    if include_block:
        inputs_origin_check(tx=tx, include_block=include_block)

    # 残高移動チェック
    if f_amount_check:
        amount_check(tx=tx, payfee_coin_id=payfee_coin_id)

    # 署名チェック
    if f_signature_check:
        if tx.hash not in signature_cashe:
            signature_check(tx=tx)
            signature_cashe.append(tx.hash)

    # Feeチェック
    if f_minimum_fee_check:
        if tx.gas_amount < tx.getsize():
            raise BlockChainError('Too low fee [{}<{}]'
                                  .format(tx.gas_price * tx.gas_amount, tx.getsize()))

    # TX size チェック
    if f_size_check:
        if tx.getsize() > C.SIZE_TX_LIMIT:
            raise BlockChainError('TX size is too large. [{}>{}]'.format(tx.getsize(), C.SIZE_TX_LIMIT))

    logging.debug("Checked tx {} {}".format(C.txtype2name[tx.type], hexlify(tx.hash).decode()))


def check_tx_time(tx):
    # For unconfirmed tx
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    if tx.time > now + C.ACCEPT_MARGIN_TIME:
        raise BlockChainError('TX time too early. {}>{}+{}'
                              .format(tx.time, now, C.ACCEPT_MARGIN_TIME))
    elif tx.deadline - tx.time < 10800:
        raise BlockChainError('TX acceptable spam is too short. {}-{}<{}'
                              .format(tx.deadline, tx.time, 10800))
    elif tx.deadline < now - C.ACCEPT_MARGIN_TIME:
        raise BlockChainError('TX time is too late. [{}<{}-{}]'
                              .format(tx.deadline, now, C.ACCEPT_MARGIN_TIME))
