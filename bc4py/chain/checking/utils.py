from bc4py.config import C, V, BlockChainError
from bc4py.database.builder import builder, tx_box
from bc4py.database.tools import get_tx_with_usedindex, get_contract_storage
from bc4py.user import CoinObject
from nem_ed25519.base import Encryption
from nem_ed25519.key import is_address
from binascii import hexlify


def inputs_origin_check(tx, include_block):
    # Blockに取り込まれているなら
    # TXのInputsも既に取り込まれているはずだ
    for txhash, txindex in tx.inputs:
        input_tx = get_tx_with_usedindex(txhash=txhash, best_block=include_block)
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
        else:
            # InputのOriginは既に取り込まれている
            pass  # OK
        # 使用済みかチェック
        # TODO: 正しく機能するか？
        if txindex in input_tx.used_index:
            raise BlockChainError('Inout is already used! {}:{}'.format(hexlify(txhash).decode(), txindex))


def amount_check(tx, payfee_coin_id):
    # Inputs
    input_coins = CoinObject()
    for txhash, txindex in tx.inputs:
        input_tx = tx_box.get_tx(txhash)
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
        input_tx = tx_box.get_tx(txhash)
        address, coin_id, amount = input_tx.outputs[txindex]
        if is_address(address, V.BLOCK_PREFIX):
            need_cks.add(address)  # 通常のアドレスのみ
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
    cs = get_contract_storage(V.CONTRACT_VALIDATOR_ADDRESS, include_block)
    validator_cks = set()
    for k, v in cs.items():
        cmd, address = k[0], k[1:].decode()
        if cmd != 0:
            pass
        elif v == b'\x01':
            validator_cks.add(address)
    required_num = len(validator_cks) * 3 // 4 + 1  # TODO:数
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
    "validator_check"
]
