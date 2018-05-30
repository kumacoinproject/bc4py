from bc4py.config import V, P, BlockChainError
from bc4py.database.create import create_db, closing
from bc4py.database.chain.read import max_block_height, read_block_object, read_best_block_on_chain, read_txhash_of_block
from bc4py.database.chain.read import fill_tx_objects, read_tx_object


def _best_info():
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        chain_cur = chain_db.cursor()
        top_height = max_block_height(cur=chain_cur)
        best_block = read_best_block_on_chain(height=top_height, cur=chain_cur)
        fill_tx_objects(block=best_block, cur=chain_cur)
        best_block.bits2target()
        best_block.target2diff()
        send_data = {
            'hash': best_block.hash,
            'block': best_block.b,
            'height': best_block.height,
            'flag': best_block.flag,
            'difficulty': best_block.difficulty,
            'txs': [tx.hash for tx in best_block.txs],
            'booting': P.F_NOW_BOOTING}
        return send_data


def _block_by_hash(blockhash):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        chain_cur = chain_db.cursor()
        block = read_block_object(blockhash=blockhash, cur=chain_cur, f_fill_tx=True)
        block.bits2target()
        block.target2diff()
        txs = read_txhash_of_block(blockhash=block.hash, cur=chain_cur)
        send_data = {
            'block': block.b,
            'height': block.height,
            'flag': block.flag,
            'orphan': block.f_orphan,
            'next_hash': block.next_hash,
            'difficulty': block.difficulty,
            'txs': txs}
        return send_data


def _tx_by_hash(txhash):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        chain_cur = chain_db.cursor()
        tx = read_tx_object(txhash=txhash, cur=chain_cur)
        send_data = {
            'tx': tx.b,
            'height': tx.height,
            'type': tx.type,
            'sign': tx.signature}
        return send_data


def _unconfirmed_tx():
    send_data = {
        'txs': list(P.UNCONFIRMED_TX)}
    return send_data


class DirectCmd:
    BEST_INFO = 'cmd/best-info'
    # BLOCK_BY_HEIGHT = 'cmd/block-by-height'
    BLOCK_BY_HASH = 'cmd/block-by-hash'
    TX_BY_HASH = 'cmd/tx-by-hash'
    UNCONFIRMED_TX = 'cmd/unconfirmed-tx'

    @staticmethod
    def best_info(data):
        try:
            return _best_info()
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def block_by_hash(data):
        if 'blockhash' not in data:
            return None
        elif not isinstance(data['blockhash'], bytes):
            return None
        try:
            return _block_by_hash(blockhash=data['blockhash'])
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def tx_by_hash(data):
        if 'txhash' not in data:
            return None
        elif not isinstance(data['txhash'], bytes):
            return None
        try:
            return _tx_by_hash(txhash=data['txhash'])
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def unconfirmed_tx(data):
        try:
            return _unconfirmed_tx()
        except BlockChainError as e:
            return str(e)
