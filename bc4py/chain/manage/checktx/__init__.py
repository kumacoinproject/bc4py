from bc4py.config import C, V, BlockChainError
from .others import amount_check, inputs_origin_check, signature_check
from .tx_pos_reward import check_tx_pos_reward
from .tx_pow_rewad import check_tx_pow_reward
from .tx_mint_coin import check_tx_mint_coin
from .tx_contract import *
import logging
from binascii import hexlify
import time


def check_tx(tx, include_block, cur):
    # TXの正当性チェック
    f_amount_check = True
    f_signature_check = True
    f_size_check = True
    f_minimum_fee_check = True
    payfee_coin_id = 0
    now = int(time.time()) - V.BLOCK_GENESIS_TIME

    # 共通検査
    if include_block:
        # tx is included block
        if tx not in include_block.txs:
            raise BlockChainError('BLock not include the tx.')
        elif not (tx.time <= include_block.time <= tx.deadline):
            raise BlockChainError('block time isn\'t include in TX time-deadline. [{}<={}<={}]'
                                  .format(tx.time, include_block.time, tx.deadline))
    else:
        # Unconfirmed tx
        now = int(time.time())-V.BLOCK_GENESIS_TIME
        if now+C.ACCEPT_MARGIN_TIME < tx.time:
            raise BlockChainError("Unconfirmed tx is too future. [{}+{}<{}]"
                                  .format(now, C.ACCEPT_MARGIN_TIME, tx.time))
        elif tx.deadline < now-C.ACCEPT_MARGIN_TIME:
            raise BlockChainError("Unconfirmed tx is too past. [{}<{}-{}]"
                                  .format(tx.deadline, now, C.ACCEPT_MARGIN_TIME))
        elif tx.deadline-tx.time < 10800:
            raise BlockChainError("Unconfirmed tx is too short retention. [{}-{}<10800]"
                                  .format(tx.deadline, tx.time))

    # 各々のタイプで検査
    if tx.type == C.TX_GENESIS:
        f_amount_check = False
        f_signature_check = False
        f_size_check = False
        f_minimum_fee_check = False
        if tx.height != 0:
            raise BlockChainError('Genesis tx is height 0. {}'.format(tx.height))

    elif tx.type == C.TX_POS_REWARD:
        f_amount_check = False
        f_minimum_fee_check = False
        check_tx_pos_reward(tx=tx, include_block=include_block, cur=cur)

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
        elif not (now + C.ACCEPT_MARGIN_TIME >= tx.time <= tx.deadline - 10800):
            raise BlockChainError('TX time is wrong 2. [{}>={}-5<={}-10800]'.format(now, tx.time, tx.deadline))
        elif include_block and 0 == include_block.txs.index(tx):
            raise BlockChainError('tx index is not proof tx.')

    elif tx.type == C.TX_MINT_COIN:
        f_amount_check = False
        f_minimum_fee_check = False
        check_tx_mint_coin(tx=tx, include_block=include_block, cur=cur)

    elif tx.type == C.TX_CREATE_CONTRACT:
        f_minimum_fee_check = False
        check_tx_create_contract(tx=tx)

    elif tx.type == C.TX_START_CONTRACT:
        check_tx_start_contract(start_tx=tx, include_block=include_block, cur=cur)

    elif tx.type == C.TX_FINISH_CONTRACT:
        if include_block:
            f_signature_check = False
            f_minimum_fee_check = False
            check_tx_finish_contract(finish_tx=tx, include_block=include_block)
        else:
            raise BlockChainError('Not allow finish tx no block.')
    else:
        raise BlockChainError('Unknown tx type "{}"'.format(tx.type))

    # Inputs origin チェック
    if include_block:
        inputs_origin_check(tx=tx, include_block=include_block, cur=cur)

    # 残高移動チェック
    if f_amount_check:
        amount_check(tx=tx, payfee_coin_id=payfee_coin_id, cur=cur)

    # 署名チェック
    if f_signature_check:
        signature_check(tx=tx, cur=cur)

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
