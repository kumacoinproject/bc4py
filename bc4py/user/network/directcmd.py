from bc4py.config import P, BlockChainError
from bc4py.database import obj


"""
: Peer2Peer DirectCmd definition
return string => ERROR
return others => SUCCESS
"""


class DirectCmd(object):

    @staticmethod
    def best_info(user, data):
        """return best info of chain"""
        try:
            if obj.chain_builder.best_block:
                return {
                    'hash': obj.chain_builder.best_block.hash,
                    'height': obj.chain_builder.best_block.height,
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
    def block_by_height(user, data):
        height = data.get('height')
        if height is None:
            return 'do not find key "height"'
        if not isinstance(height, int):
            return f"height is not int! {height}"
        try:
            block = obj.chain_builder.get_block(height=height)
            if block:
                return block
            else:
                return f"Not found block height {height}"
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def block_by_hash(user, data):
        blockhash = data.get('blockhash')
        if blockhash is None:
            return 'do not find key "blockhash"'
        if not isinstance(blockhash, bytes):
            return f"blockhash is not bytes! {blockhash}"
        try:
            block = obj.chain_builder.get_block(blockhash=blockhash)
            if block is None:
                return f"Not found blockhash {blockhash.hex()}"
            return block
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def tx_by_hash(user, data):
        txhash = data.get('txhash')
        if txhash is None:
            return 'do not find key "txhash"'
        elif not isinstance(txhash, bytes):
            return f"txhash is not bytes! {txhash}"
        try:
            tx = obj.tx_builder.get_memorized_tx(txhash)
            if tx is None:
                return f"Not found tx {txhash.hex()}"
            return tx
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def unconfirmed_tx(user, data):
        try:
            return {
                'txs': list(obj.tx_builder.unconfirmed.keys()),
            }
        except BlockChainError as e:
            print("exception! unconfirmed", user, e)
            return str(e)

    @staticmethod
    def big_blocks(user, data):
        try:
            index_height = data.get('height')
            if index_height is None:
                return 'do not find key "height"'
            request_len = data.get('request_len', 20)
            request_len = max(0, min(100, request_len))
            if not isinstance(request_len, int):
                return f"request_len is int! {request_len}"
            data = list()
            for height in range(index_height, index_height + max(0, request_len)):
                block = obj.chain_builder.get_block(height=height)
                if block is None:
                    break
                data.append(block)
            return data
        except BlockChainError as e:
            return str(e)


__all__ = [
    "DirectCmd",
]
