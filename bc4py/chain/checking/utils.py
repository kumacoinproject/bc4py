from bc4py.config import C, V, BlockChainError
from bc4py.database.builder import builder, tx_builder
from bc4py.database.tools import get_usedindex
from bc4py.user import CoinObject
from nem_ed25519.base import Encryption
from nem_ed25519.key import is_address
from binascii import hexlify


def inputs_origin_check(tx, include_block):
    # Blockに取り込まれているなら
    # TXのInputsも既に取り込まれているはずだ
    limit_height = builder.best_block.height - C.MATURE_HEIGHT
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            # InputのOriginが存在しない
            raise BlockChainError('Not found input tx. {}:{}'.format(hexlify(txhash).decode(), txindex))
        elif input_tx.height is None:
            # InputのOriginはUnconfirmed
            if include_block:
                raise BlockChainError('TX {} is include'
                                      ', but input origin {} is unconfirmed.'.format(tx, input_tx))
            else:
                # UnconfirmedTXの受け入れなので、txもinput_txもUnconfirmed
                pass  # OK
        elif input_tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD) and \
                input_tx.height > limit_height:
            raise BlockChainError('input origin is proof tx, {}>{}'.format(input_tx.height, limit_height))
        else:
            # InputのOriginは既に取り込まれている
            pass  # OK
        # 使用済みかチェック
        if txindex in get_usedindex(txhash, include_block):
            raise BlockChainError('Input of {} is already used! {}:{}'
                                  .format(tx, hexlify(txhash).decode(), txindex))


def amount_check(tx, payfee_coin_id):
    # Inputs
    input_coins = CoinObject()
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            raise BlockChainError('Not found input tx {}'.format(hexlify(txhash).decode()))
        address, coin_id, amount = input_tx.outputs[txindex]
        input_coins[coin_id] += amount

    # Outputs
    output_coins = CoinObject()
    for address, coin_id, amount in tx.outputs:
        if amount <= 0:
            raise BlockChainError('Input amount is more than 0')
        output_coins[coin_id] += amount

    # Fee
    fee_coins = CoinObject(coin_id=payfee_coin_id, amount=tx.gas_price*tx.gas_amount)

    # Check all plus amount
    remain_amount = input_coins - output_coins - fee_coins
    if not remain_amount.is_all_plus_amount():
        raise BlockChainError('There are minus amount coins. {}={}-{}-{}'
                              .format(remain_amount, input_coins, output_coins, fee_coins))


def signature_check(tx):
    need_cks = set()
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            raise BlockChainError('Not found input tx {}'.format(hexlify(txhash).decode()))
        address, coin_id, amount = input_tx.outputs[txindex]
        if is_address(address, V.BLOCK_PREFIX):
            need_cks.add(address)  # 通常のアドレスのみ
        else:
            raise BlockChainError('Not common address {} {}.'.format(address, tx))
    signed_cks = set()
    ecc = Encryption(prefix=V.BLOCK_PREFIX)
    for pubkey, signature in tx.signature:
        try:
            ecc.pk = pubkey
            ecc.verify(msg=tx.b, signature=signature)
            ecc.get_address()
            signed_cks.add(ecc.ck)
        except BaseException as e:
            raise BlockChainError('Signature verification failed. "{}"'.format(e))

    if need_cks != signed_cks:
        raise BlockChainError('Signed list check is failed. [{}={}]'.format(need_cks, signed_cks))


def validator_check(tx, include_block):
    assert tx.type == C.TX_FINISH_CONTRACT, 'validator_check is for FinishTX.'
    validator_cks, required_num = get_validator_info(include_block)
    signed_cks = set()
    already_signed_num = tx.inner_params.get('signed_num', 0)
    ecc = Encryption(prefix=V.BLOCK_PREFIX)
    for pubkey, signature in tx.signature:
        try:
            ecc.pk = pubkey
            ecc.verify(msg=tx.b, signature=signature)
            ecc.get_address()
            signed_cks.add(ecc.ck)
        except BaseException as e:
            raise BlockChainError('Signature verification failed. "{}"'.format(e))

    if include_block:
        if required_num > len(validator_cks & signed_cks):
            raise BlockChainError('Not satisfied required sign num. [{}>{}&{}]'
                                  .format(required_num, len(validator_cks), len(signed_cks)))
    else:
        if already_signed_num >= len(validator_cks & signed_cks):
            raise BlockChainError('')
        tx.inner_params['signed_num'] = len(validator_cks & signed_cks)


__all__ = [
    "inputs_origin_check",
    "amount_check",
    "signature_check",
    "validator_check",
]
