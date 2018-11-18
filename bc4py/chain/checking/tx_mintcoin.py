from bc4py.config import C, V, BlockChainError
from bc4py.chain.checking.signature import *
from bc4py.database.mintcoin import *
from bc4py.database.builder import tx_builder
from bc4py.user import CoinObject
from binascii import hexlify
import bjson


"""def check_tx_mint_coin_old(tx, include_block):
    if not (0 < len(tx.inputs) and 0 < len(tx.outputs) <= 2):
        raise BlockChainError('Input and output is more than 1.')
    elif tx.message_type != C.MSG_BYTE:
        raise BlockChainError('TX_MINT_COIN message is bytes.')
    elif include_block and 0 == include_block.txs.index(tx):
        raise BlockChainError('tx index is not proof tx.')
    elif tx.gas_amount < tx.getsize() + C.MINTCOIN_GAS:
        raise BlockChainError('Insufficient gas amount [{}<{}+{}]'
                              .format(tx.gas_amount, tx.getsize(), C.MINTCOIN_GAS))

    coins = CoinObject()
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            raise BlockChainError('Not found BaseTX {} of {}'.format(hexlify(txhash).decode(), tx))
        address, coin_id, amount = input_tx.outputs[txindex]
        coins[coin_id] += amount
        if coin_id != 0:
            raise BlockChainError('TX_MINT_COIN inputs are all coinID 0. {}'.format(coin_id))

    for address, coin_id, amount in tx.outputs:
        coins[coin_id] -= amount
    payfee_coin_id = 0
    coins[payfee_coin_id] -= tx.gas_amount * tx.gas_price

    if sum(coins.values()) < 0:
        print(tx.getinfo())
        raise BlockChainError('mintcoin amount sum is {}'.format(sum(coins.values())))

    mint = MintCoinObject(txhash=tx.hash, binary=tx.message)
    mint_id = get_mint_id_from_tx(coins)
    if mint_id:
        # 追加発行あり
        if set(coins.keys()) != {0, mint_id}:
            raise BlockChainError('Allowed two coin_ids [{}!={}]'.format(set(coins.keys()), {0, mint_id}))
        if mint_id != mint.coin_id:
            raise BlockChainError('Differ coin_id [{}!={}]'.format(mint_id, mint.coin_id))
        elif coins[mint_id] * -1 != mint.amount:
            raise BlockChainError('Differ amount [{}!={}]'.format(coins[mint_id]*-1, mint.amount))
    else:
        # 追加発行なし
        if set(coins.keys()) != {0}:
            raise BlockChainError('Allowed one coin_id [{}!={}]'.format(set(coins.keys()), {0}))
        if mint.amount != 0:
            raise BlockChainError('No amount [{}!=0]'.format(mint.amount))
        mint_id = mint.coin_id

    try:
        # 読み込んでおかしなところがなければOK
        old_mint = get_mintcoin(mint_id=mint_id, best_block=include_block)
        if include_block is None:
            mint.marge(old_mint)
    except MintCoinError as e:
        raise BlockChainError('Failed check mint coin "{}"'.format(e))


def get_mint_id_from_tx(coins):
    mint_id_set = set(coins.keys()).difference({0})
    if len(mint_id_set) != 1:
        return None
    return mint_id_set.pop()"""


def check_tx_mint_coin(tx, include_block):
    if not (0 < len(tx.inputs) and 0 < len(tx.outputs)):
        raise BlockChainError('Input and output is more than 1.')
    elif tx.message_type != C.MSG_BYTE:
        raise BlockChainError('TX_MINT_COIN message is bytes.')
    elif include_block and 0 == include_block.txs.index(tx):
        raise BlockChainError('tx index is not proof tx.')
    elif tx.gas_amount < tx.getsize() + C.MINTCOIN_GAS:
        raise BlockChainError('Insufficient gas amount [{}<{}+{}]'
                              .format(tx.gas_amount, tx.getsize(), C.MINTCOIN_GAS))
    # check new mintcoin format
    try:
        mint_id, params, setting = bjson.loads(tx.message)
    except Exception as e:
        raise BlockChainError('BjsoDecodeError: {}'.format(e))
    m_before = get_mintcoin_object(coin_id=mint_id, best_block=include_block, stop_txhash=tx.hash)
    result = check_mintcoin_new_format(m_before=m_before, new_params=params, new_setting=setting)
    if isinstance(result, str):
        raise BlockChainError('Failed check mintcoin block={}: {}'.format(include_block, result))
    # signature check
    require_cks, coins = input_output_digest(tx=tx)
    owner_address = m_before.address
    if owner_address:
        require_cks.add(owner_address)
    signed_cks = get_signed_cks(tx)
    if signed_cks != require_cks:
        raise BlockChainError('Signature check failed. signed={} require={} lack={}'
                              .format(signed_cks, require_cks, require_cks-signed_cks))
    # amount check
    if 0 < len(set(coins.keys()) - {0, mint_id}):
        raise BlockChainError('Unexpected coin_id included. {}'.format(set(coins.keys()) - {0, mint_id}))
    if mint_id in coins:
        # increase/decrease mintcoin amount
        if not m_before.setting['additional_issue']:
            raise BlockChainError('additional_issue is False but change amount.')
        if coins[0] + coins[mint_id] < 0:
            raise BlockChainError('Too many output amount. {}'.format(coins))
        if coins[mint_id] < 0:
            pass  # increase
        if coins[mint_id] > 0:
            pass  # decrease
    else:
        # only change mintcoin status
        if sum(coins.values()) < 0:
            raise BlockChainError('Too many output amount. {}'.format(coins))


def input_output_digest(tx):
    require_cks = set()
    coins = CoinObject()
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash=txhash)
        if input_tx is None:
            raise BlockChainError('input tx is None. {}:{}'.format(hexlify(txhash).decode(), txindex))
        address, coin_id, amount = input_tx.outputs[txindex]
        require_cks.add(address)
        coins[coin_id] += amount
    coins[0] -= tx.gas_amount * tx.gas_price
    for address, coin_id, amount in tx.outputs:
        coins[coin_id] -= amount
    return require_cks, coins


__all__ = [
    "check_tx_mint_coin",
]
