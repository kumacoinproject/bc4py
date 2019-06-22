from bc4py.config import V, P, BlockChainError
from bc4py.database.builder import chain_builder, tx_builder


"""
: Peer2Peer DirectCmd definition
return string => ERROR
return others => SUCCESS
"""


class DirectCmd(object):
    BEST_INFO = 'cmd/v1/best-info'
    BLOCK_BY_HEIGHT = 'cmd/v1/block-by-height'
    BLOCK_BY_HASH = 'cmd/v1/block-by-hash'
    TX_BY_HASH = 'cmd/v1/tx-by-hash'
    UNCONFIRMED_TX = 'cmd/v1/unconfirmed-tx'
    BIG_BLOCKS = 'cmd/v1/big-block'

    @staticmethod
    def best_info(data):
        """return best info of chain"""
        try:
            if chain_builder.best_block:
                return {
                    'hash': chain_builder.best_block.hash,
                    'height': chain_builder.best_block.height,
                    'booting': P.F_NOW_BOOTING,
                }
            else:
                return {
                    'hash': None,
                    'height': None,
                    'booting': True,
                }
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def block_by_height(data):
        height = data.get('height')
        if height is None:
            return 'do not find key "height"'
        if not isinstance(height, int):
            return f"height is not int! {height}"
        try:
            block = chain_builder.get_block(height=height)
            if block:
                return block
            else:
                return f"Not found block height {height}"
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def block_by_hash(data):
        blockhash = data.get('blockhash')
        if blockhash is None:
            return 'do not find key "blockhash"'
        if not isinstance(blockhash, bytes):
            return f"blockhash is not bytes! {blockhash}"
        try:
            block = chain_builder.get_block(blockhash=blockhash)
            if block is None:
                return f"Not found blockhash {blockhash.hex()}"
            return block
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def tx_by_hash(data):
        txhash = data.get('txhash')
        if txhash is None:
            return 'do not find key "txhash"'
        elif not isinstance(txhash, bytes):
            return f"txhash is not bytes! {txhash}"
        try:
            tx = tx_builder.get_tx(txhash=txhash)
            if tx is None:
                return f"Not found tx {txhash.hex()}"
            return tx
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def unconfirmed_tx(data):
        try:
            return {
                'txs': list(tx_builder.unconfirmed.keys()),
            }
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def big_blocks(data):
        try:
            index_height = data.get('data')
            request_len = data.get('request_len', 20)
            if data is None:
                return 'do not find key "height"'
            if not isinstance(request_len, int):
                return f"request_len is int! {request_len}"
            data = list()
            for height in range(index_height, index_height + max(0, request_len)):
                block = chain_builder.get_block(height=height)
                if block is None:
                    break
                data.append(block)
            return data
        except BlockChainError as e:
            return str(e)
