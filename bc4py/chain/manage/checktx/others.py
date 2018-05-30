from bc4py.config import C, V, BlockChainError
from bc4py.database.chain.read import read_tx_output, fill_tx_objects, read_tx_object, read_best_block_on_chain
from bc4py.user import CoinObject
from nem_ed25519.base import Encryption
from nem_ed25519.key import is_address
from binascii import hexlify


def inputs_origin_check(tx, include_block, cur):
    # Blockに取り込まれているなら
    # TXのInputsも既に取り込まれているはずだ
    for txhash, txindex in tx.inputs:
        input_tx = read_tx_object(txhash=txhash, cur=cur)
        if input_tx.height is None:
            # txhashが既にBlockに取り込まれ、若いTXならセーフ
            input_index = get_blockindex_by_txhash(block=include_block, txhash=txhash)
            if input_index is None:
                raise BlockChainError('inputs tx origin is not include block. {}'.format(tx))
            elif input_index > include_block.txs.index(tx):
                # 必要？
                raise BlockChainError('index of txhash({}) is higher than input tx. {}'
                                      .format(hexlify(txhash).decode(), tx))
            else:
                input_tx.height = include_block.height
        else:
            block = read_best_block_on_chain(height=input_tx.height, cur=cur)
            fill_tx_objects(block=block, cur=cur)
            for block_tx in block.txs:
                if input_tx.hash == block_tx.hash:
                    break
            else:
                raise BlockChainError('Cannot find {} in main chain. [{} not in {}]'
                                      .format(tx, input_tx, block))


def get_blockindex_by_txhash(block, txhash):
    for index, tx in enumerate(block.txs):
        if tx.hash == txhash:
            return index
    return None


def amount_check(tx, payfee_coin_id, cur):
    # Inputs
    input_coins = CoinObject()
    for txhash, txindex in tx.inputs:
        address, coin_id, amount = read_tx_output(txhash, txindex, cur)
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


def signature_check(tx, cur):
    need_cks = set()
    signed_cks = set()
    ecc = Encryption(prefix=V.BLOCK_PREFIX)
    for txhash, txindex in tx.inputs:
        address, coin_id, amount = read_tx_output(txhash, txindex, cur)
        if is_address(address, V.BLOCK_PREFIX):
            need_cks.add(address)  # 通常のアドレスのみ
    for pubkey, signature in tx.signature:
        try:
            ecc.pk = pubkey
            ecc.verify(msg=tx.b, signature=signature)
            ecc.get_address()
            signed_cks.add(ecc.ck)
        except BaseException as e:
            raise BlockChainError('Signature verification failed. {}'.format(e))

    if need_cks != signed_cks:
        raise BlockChainError('Signed list check is failed. [{}={}]'.format(need_cks, signed_cks))
