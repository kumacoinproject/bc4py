from bc4py.config import V
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
import os
import bjson
import logging


def create_boot_file(genesis_block, connections=None):
    data = {
        'block': genesis_block.b,
        'txs': [tx.b for tx in genesis_block.txs],
        'connections': connections or list()}
    boot_path = os.path.join(V.DB_HOME_DIR, 'boot.dat')
    with open(boot_path, mode='bw') as fp:
        bjson.dump(data, fp, compress=False)
    logging.info("create new boot.dat!")


def load_boot_file():
    normal_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'boot.dat')
    extra_path = os.path.join(V.DB_HOME_DIR, 'boot.dat')
    if os.path.exists(normal_path):
        with open(normal_path, mode='br') as fp:
            data = bjson.load(fp=fp)
    elif os.path.exists(extra_path):
        with open(extra_path, mode='br') as fp:
            data = bjson.load(fp=fp)
    else:
        raise FileNotFoundError('Cannot find boot.dat "{}" or "{}" ?'.format(normal_path, extra_path))
    genesis_block = Block(binary=data['block'])
    genesis_block.height = 0
    for b_tx in data['txs']:
        tx = TX(binary=b_tx)
        tx.height = 0
        genesis_block.txs.append(tx)
    connections = data.get('connections', list())
    return genesis_block, connections
