from bc4py.config import C, V, BlockChainError
from bc4py.chain.mintcoin import MintCoinObject, MintCoinError
from bc4py.database.chain.read import read_tx_output, read_mint_coin
from bc4py.user import CoinObject


def check_tx_mint_coin(tx, include_block, cur):
    if not (len(tx.inputs) > 0 and len(tx.outputs) > 0):
        raise BlockChainError('Input and output is more than 1.')
    elif tx.message_type != C.MSG_BYTE:
        raise BlockChainError('TX_MINT_COIN message is bytes.')
    elif include_block and 0 == include_block.txs.index(tx):
        raise BlockChainError('tx index is not proof tx.')
    elif tx.gas_amount < tx.getsize() + C.MINTCOIN_FEE:
        raise BlockChainError('Insufficient gas amount [{}<{}+{}]'
                              .format(tx.gas_amount, tx.getsize(), C.MINTCOIN_FEE))

    coins = CoinObject()
    for txhash, txindex in tx.inputs:
        address, coin_id, amount = read_tx_output(txhash, txindex, cur)
        coins[coin_id] += amount
        if coin_id != 0:
            raise BlockChainError('TX_MINT_COIN inputs are all coinID 0. {}'.format(coin_id))

    for address, coin_id, amount in tx.outputs:
        coins[coin_id] -= amount
    payfee_coin_id = 0
    coins[payfee_coin_id] -= tx.gas_amount*tx.gas_price

    if sum(coins.values()) < 0:
        print(tx.getinfo())
        raise BlockChainError('mintcoin amount sum is {}'.format(sum(coins.values())))

    mint = MintCoinObject(None, binary=tx.message)
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
        read_mint_coin(mint_id, cur)
    except MintCoinError as e:
        raise BlockChainError('Failed check mint coin "{}"'.format(e))


def get_mint_id_from_tx(coins):
    mint_id_set = set(coins.keys()).difference({0})
    if len(mint_id_set) != 1:
        return None
    return mint_id_set.pop()
