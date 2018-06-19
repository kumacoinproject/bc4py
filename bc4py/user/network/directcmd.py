from bc4py.config import V, P, BlockChainError
from bc4py.database.create import create_db, closing
from bc4py.database.builder import builder, tx_builder
from binascii import hexlify


def _best_info():
    best_block = builder.best_block
    if not best_block.difficulty:
        best_block.bits2target()
        best_block.target2diff()
    txs = [{
            'tx': tx.b,
            'sign': tx.signature}
        for tx in best_block.txs]
    send_data = {
        'hash': best_block.hash,
        'block': best_block.b,
        'height': best_block.height,
        'flag': best_block.flag,
        'difficulty': best_block.difficulty,
        'txs': txs,
        'booting': P.F_NOW_BOOTING}
    return send_data


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
    if not block.difficulty:
        block.bits2target()
        block.target2diff()
    txs = [{
        'tx': tx.b,
        'sign': tx.signature}
        for tx in block.txs]
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
    tx = tx_builder.get_tx(txhash)
    if tx is None:
        return 'Not found tx {}.'.format(hexlify(txhash).decode())
    send_data = {
        'tx': tx.b,
        'height': tx.height,
        'sign': tx.signature}
    return send_data


def _unconfirmed_tx():
    send_data = [{
        'tx': tx.b,
        'sign': tx.signature} for tx in tx_builder.unconfirmed.values()]
    return send_data


class DirectCmd:
    BEST_INFO = 'cmd/best-info'
    BLOCK_BY_HEIGHT = 'cmd/block-by-height'
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
