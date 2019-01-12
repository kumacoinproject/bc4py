from bc4py.config import C, V, BlockChainError
from bc4py.chain.checking.tx_reward import *
from bc4py.chain.checking.tx_mintcoin import *
from bc4py.chain.checking.tx_contract import *
from bc4py.chain.checking.utils import *
from logging import getLogger
from binascii import hexlify
from time import time


log = getLogger('bc4py')


def check_tx(tx, include_block):
    # TXの正当性チェック
    f_inputs_origin_check = True
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
        f_signature_check = False
        check_tx_mint_coin(tx=tx, include_block=include_block)

    elif tx.type == C.TX_VALIDATOR_EDIT:
        f_signature_check = False
        f_minimum_fee_check = False
        check_tx_validator_edit(tx=tx, include_block=include_block)

    elif tx.type == C.TX_CONCLUDE_CONTRACT:
        f_signature_check = False
        f_minimum_fee_check = False
        check_tx_contract_conclude(tx=tx, include_block=include_block)

    else:
        raise BlockChainError('Unknown tx type "{}"'.format(tx.type))

    # Inputs origin チェック
    if f_inputs_origin_check:
        inputs_origin_check(tx=tx, include_block=include_block)

    # 残高移動チェック
    if f_amount_check:
        amount_check(tx=tx, payfee_coin_id=payfee_coin_id)

    # 署名チェック
    if f_signature_check:
        signature_check(tx=tx)

    # Feeチェック
    if f_minimum_fee_check:
        if tx.gas_amount < tx.size + C.SIGNATURE_GAS * len(tx.signature):
            raise BlockChainError('Too low fee [{}<{}+{}]'.format(
                tx.gas_amount, tx.size, C.SIGNATURE_GAS*len(tx.signature)))

    # TX size チェック
    if f_size_check:
        if tx.size > C.SIZE_TX_LIMIT:
            raise BlockChainError('TX size is too large. [{}>{}]'.format(tx.size, C.SIZE_TX_LIMIT))

    if include_block:
        log.info("Checked tx {}".format(tx))
    else:
        log.debug("Check unconfirmed tx {}".format(hexlify(tx.hash).decode()))


def check_tx_time(tx):
    # For unconfirmed tx
    now = int(time()) - V.BLOCK_GENESIS_TIME
    if tx.type in (C.TX_VALIDATOR_EDIT, C.TX_CONCLUDE_CONTRACT):
        if not (tx.time - C.ACCEPT_MARGIN_TIME < now < tx.deadline + C.ACCEPT_MARGIN_TIME):
            raise BlockChainError('TX time is not correct range. {}<{}<{}'
                                  .format(tx.time-C.ACCEPT_MARGIN_TIME, now, tx.deadline+C.ACCEPT_MARGIN_TIME))
    else:
        if tx.time > now + C.ACCEPT_MARGIN_TIME:
            raise BlockChainError('TX time too early. {}>{}+{}'
                                  .format(tx.time, now, C.ACCEPT_MARGIN_TIME))
        if tx.deadline < now - C.ACCEPT_MARGIN_TIME:
            raise BlockChainError('TX time is too late. [{}<{}-{}]'
                                  .format(tx.deadline, now, C.ACCEPT_MARGIN_TIME))
    # common check
    if tx.deadline - tx.time < 10800:
        raise BlockChainError('TX acceptable spam is too short. {}-{}<{}'
                              .format(tx.deadline, tx.time, 10800))
    if tx.deadline - tx.time > 43200:  # 12hours
        raise BlockChainError('TX acceptable spam is too long. {}-{}<{}'
                              .format(tx.deadline, tx.time, 10800))
