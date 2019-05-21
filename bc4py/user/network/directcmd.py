from bc4py.config import V, P, BlockChainError
from bc4py.database.builder import chain_builder, tx_builder


def _best_info():
    if chain_builder.best_block:
        return {'hash': chain_builder.best_block.hash, 'height': chain_builder.best_block.height, 'booting': P.F_NOW_BOOTING}
    else:
        return {'hash': None, 'height': None, 'booting': True}


def _block_by_height(height):
    block = chain_builder.get_block(height=height)
    if block:
        return block
    else:
        return 'Not found block height {}'.format(height)


def _block_by_hash(blockhash):
    block = chain_builder.get_block(blockhash=blockhash)
    if block is None:
        return 'Not found blockhash {}'.format(blockhash.hex())
    return block


def _tx_by_hash(txhash):
    tx = tx_builder.get_tx(txhash=txhash)
    if tx is None:
        return 'Not found tx {}'.format(txhash.hex())
    return tx


def _unconfirmed_tx():
    return {'txs': list(tx_builder.unconfirmed.keys())}


def _big_blocks(index_height):
    data = list()
    for height in range(index_height, index_height + 20):
        block = chain_builder.get_block(height=height)
        if block is None:
            break
        data.append(block)
    # TODO:一度に送信できるBytesにチェック
    return data


class DirectCmd(object):
    BEST_INFO = 'cmd/v1/best-info'
    BLOCK_BY_HEIGHT = 'cmd/v1/block-by-height'
    BLOCK_BY_HASH = 'cmd/v1/block-by-hash'
    TX_BY_HASH = 'cmd/v1/tx-by-hash'
    UNCONFIRMED_TX = 'cmd/v1/unconfirmed-tx'
    BIG_BLOCKS = 'cmd/v1/big-block'

    @staticmethod
    def best_info(data):
        try:
            return _best_info()
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def block_by_height(data):
        if 'height' not in data:
            return 'do not find key "height"'
        elif not isinstance(data['height'], int):
            return 'height is not int! {}'.format(type(data['height']))
        try:
            return _block_by_height(height=data['height'])
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def block_by_hash(data):
        if 'blockhash' not in data:
            return 'do not find key "blockhash"'
        elif not isinstance(data['blockhash'], bytes):
            return 'blockhash is not bytes! {}'.format(type(data['blockhash']))
        try:
            return _block_by_hash(blockhash=data['blockhash'])
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def tx_by_hash(data):
        if 'txhash' not in data:
            return 'do not find key "txhash"'
        elif not isinstance(data['txhash'], bytes):
            return 'txhash is not bytes! {}'.format(type(data['txhash']))
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

    @staticmethod
    def big_blocks(data):
        try:
            if 'height' not in data:
                return 'do not find key "height"'
            else:
                return _big_blocks(index_height=data['height'])
        except BlockChainError as e:
            return str(e)
