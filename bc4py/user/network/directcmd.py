from bc4py.config import V, P, BlockChainError
from bc4py.database.builder import builder, tx_builder
from binascii import hexlify


def _best_info():
    if builder.best_block:
        txs = [{'tx': tx.b, 'sign': tx.signature} for tx in builder.best_block.txs]
        return {
            'hash': builder.best_block.hash,
            'block': builder.best_block.b,
            'height': builder.best_block.height,
            'flag': builder.best_block.flag,
            'difficulty': builder.best_block.difficulty,
            'txs': txs,
            'booting': P.F_NOW_BOOTING}
    else:
        return {
            'hash': None,
            'block': None,
            'height': None,
            'flag': None,
            'difficulty': None,
            'txs': [],
            'booting': True}


def _block_by_height(height):
    blockhash = builder.get_block_hash(height)
    if blockhash:
        return {'blockhash': blockhash}
    else:
        return 'Not found block height {}.'.format(height)


def _block_by_hash(blockhash):
    block = builder.get_block(blockhash)
    if block is None:
        return 'Not found blockhash {}.'.format(hexlify(blockhash).decode())
    txs = [{
        'tx': tx.b,
        'sign': tx.signature}
        for tx in block.txs]
    send_data = {
        'block': block.b,
        'height': block.height,
        'flag': block.flag,
        'orphan': bool(block.f_orphan is True),
        'next_hash': block.next_hash,
        'difficulty': block.difficulty,
        'txs': txs}
    return send_data


def _tx_by_hash(txhash):
    tx = tx_builder.get_tx(txhash)
    if tx is None:
        return 'Not found tx {}.'.format(hexlify(txhash).decode())
    send_data = {
        'tx': tx.b,
        'height': tx.height,
        'sign': tx.signature}
    return send_data


def _unconfirmed_tx():
    send_data = {'txs': list(tx_builder.unconfirmed.keys())}
    # send_data = [{
    #    'tx': tx.b,
    #    'sign': tx.signature} for tx in tx_builder.unconfirmed.values()]
    return send_data


def _big_blocks(height):
    data = list()
    for i in range(20):
        blockhash = builder.get_block_hash(height + i)
        if blockhash is None:
            break
        block = builder.get_block(blockhash)
        if block is None:
            break
        txs = [(tx.b, tx.signature) for tx in block.txs]
        data.append((block.b, block.height, block.flag, txs))
    # TODO:一度に送信できるBytesにチェック
    return data


class DirectCmd:
    BEST_INFO = 'cmd/best-info'
    BLOCK_BY_HEIGHT = 'cmd/block-by-height'
    BLOCK_BY_HASH = 'cmd/block-by-hash'
    TX_BY_HASH = 'cmd/tx-by-hash'
    UNCONFIRMED_TX = 'cmd/unconfirmed-tx'
    BIG_BLOCKS = 'cmd/big-block'

    @staticmethod
    def best_info(data):
        try:
            return _best_info()
        except BlockChainError as e:
            return str(e)

    @staticmethod
    def block_by_height(data):
        if 'height' not in data:
            return None
        elif not isinstance(data['height'], int):
            return None
        try:
            return _block_by_height(height=data['height'])
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

    @staticmethod
    def big_blocks(data):
        try:
            return _big_blocks(height=data['height'])
        except BlockChainError as e:
            return str(e)
