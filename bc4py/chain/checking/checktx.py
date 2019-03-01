from bc4py.config import C, V, BlockChainError
from bc4py.chain.tx import TX
from bc4py.chain.block import Block
from bc4py.chain.checking.tx_reward import *
from bc4py.chain.checking.tx_mintcoin import *
from bc4py.chain.checking.tx_contract import *
from bc4py.chain.checking.utils import *
from logging import getLogger
from time import time
from Cryptodome.Hash import RIPEMD160, SHA256


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
        # TODO: POS tx need Multisig? f_signature_check
        if include_block.flag == C.BLOCK_COIN_POS:
            check_tx_pos_reward(tx=tx, include_block=include_block)
        elif include_block.flag == C.BLOCK_CAP_POS:
            f_signature_check = False
            f_inputs_origin_check = False
            check_tx_poc_reward(tx=tx, include_block=include_block)
        else:
            raise BlockChainError('Unknown block type {}'.format(include_block.flag))

    elif tx.type == C.TX_POW_REWARD:
        f_amount_check = False
        f_signature_check = False
        f_minimum_fee_check = False
        check_tx_pow_reward(tx=tx, include_block=include_block)

    elif tx.type == C.TX_TRANSFER:
        if not (0 < len(tx.inputs) < 256 and 0 < len(tx.outputs) < 256):
            raise BlockChainError('Input and output is 1～256.')
        # payCoinFeeID is default 0, not only 0
        _address, payfee_coin_id, _amount = tx.outputs[0]

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
        signature_check(tx=tx, include_block=include_block)

    # hash-locked check
    if tx.message_type == C.MSG_HASHLOCKED:
        check_hash_locked(tx=tx)
    else:
        if tx.R != b'':
            raise BlockChainError('Not hash-locked tx R={}'.format(tx.R))

    # message type check
    if tx.message_type not in C.msg_type2name:
        raise BlockChainError('Not found message type {}'.format(tx.message_type))

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
        log.debug("Check unconfirmed tx {}".format(tx.hash.hex()))


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
    if tx.deadline - tx.time > 3600*24*30:  # 30days
        raise BlockChainError('TX acceptable spam is too long. {}-{}>{}'
                              .format(tx.deadline, tx.time, 3600*24*30))


def check_hash_locked(tx):
    if len(tx.R) == 0:
        raise BlockChainError('R of Hash-locked is None type.')
    if len(tx.R) > 64:
        raise BlockChainError('R is too large {}bytes'.format(len(tx.R)))
    size = len(tx.message)
    if size == 20:
        if RIPEMD160.new(tx.R).digest() != tx.message:
            raise BlockChainError('Hash-locked check RIPEMD160 failed.')
    elif size == 32:
        if SHA256.new(tx.R).digest() != tx.message:
            raise BlockChainError('Hash-locked check SHA256 failed.')
    else:
        raise BlockChainError('H of Hash-locked is not correct size {}'.format(size))


def check_unconfirmed_order(best_block, ordered_unconfirmed_txs):
    if len(ordered_unconfirmed_txs) == 0:
        return None
    s = time()
    dummy_proof_tx = TX()
    dummy_proof_tx.type = C.TX_POW_REWARD,
    dummy_block = Block()
    dummy_block.height = best_block.height + 1
    dummy_block.previous_hash = best_block.hash
    dummy_block.txs.append(dummy_proof_tx)  # dummy for proof tx
    dummy_block.txs.extend(ordered_unconfirmed_txs)
    tx = None
    try:
        for tx in ordered_unconfirmed_txs:
            if tx.type == C.TX_GENESIS:
                pass
            elif tx.type == C.TX_POS_REWARD:
                pass
            elif tx.type == C.TX_POW_REWARD:
                pass
            elif tx.type == C.TX_TRANSFER:
                pass
            elif tx.type == C.TX_MINT_COIN:
                check_tx_mint_coin(tx=tx, include_block=dummy_block)
            elif tx.type == C.TX_VALIDATOR_EDIT:
                check_tx_validator_edit(tx=tx, include_block=dummy_block)
            elif tx.type == C.TX_CONCLUDE_CONTRACT:
                check_tx_contract_conclude(tx=tx, include_block=dummy_block)
            else:
                raise BlockChainError('Unknown tx type "{}"'.format(tx.type))
        else:
            log.debug('Finish unconfirmed order check {}mSec'.format(int((time()-s)*1000)))
            return None
    except Exception as e:
        log.warning(e, exc_info=True)
    # return errored tx
    return tx


__all__ = [
    "check_tx",
    "check_tx_time",
    "check_hash_locked",
    "check_unconfirmed_order"
]
