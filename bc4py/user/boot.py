from bc4py.config import C, V
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.database.builder import builder, tx_builder
from bc4py.chain.checking import new_insert_block
import os
import bjson
import logging
import pickle
import random
from base64 import b64decode, b64encode


def create_boot_file(genesis_block, network_ver=None, connections=None):
    network_ver = network_ver or random.randint(1000000, 0xffffffff)
    assert isinstance(network_ver, int) and abs(network_ver) <= 0xffffffff, 'network_ver is int <=0xffffffff.'
    data = {
        'block': genesis_block.b,
        'txs': [tx.b for tx in genesis_block.txs],
        'connections': connections or list(),
        'network_ver': network_ver}
    boot_path = os.path.join(V.DB_HOME_DIR, 'boot.dat')
    data = b64encode(bjson.dumps(data))
    with open(boot_path, mode='bw') as fp:
        while len(data) > 0:
            write, data = data[:60], data[60:]
            fp.write(write+b'\n')
    logging.info("create new boot.dat!")


def load_boot_file():
    normal_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'boot.dat')
    extra_path = os.path.join(V.DB_HOME_DIR, 'boot.dat')
    if os.path.exists(normal_path):
        with open(normal_path, mode='br') as fp:
            data = bjson.loads(b64decode(fp.read().replace(b'\n', b'').replace(b'\r', b'')))
    elif os.path.exists(extra_path):
        with open(extra_path, mode='br') as fp:
            data = bjson.loads(b64decode(fp.read().replace(b'\n', b'').replace(b'\r', b'')))
    else:
        raise FileNotFoundError('Cannot find boot.dat "{}" or "{}" ?'.format(normal_path, extra_path))
    genesis_block = Block(binary=data['block'])
    genesis_block.flag = C.BLOCK_GENESIS
    genesis_block.height = 0
    for b_tx in data['txs']:
        tx = TX(binary=b_tx)
        tx.height = 0
        genesis_block.txs.append(tx)
    connections = data.get('connections', list())
    network_ver = data['network_ver']
    return genesis_block, network_ver, connections


def create_bootstrap_file():
    boot_path = os.path.join(V.DB_HOME_DIR, 'bootstrap.dat')
    with open(boot_path, mode='ba') as fp:
        for height, blockhash in builder.db.read_block_hash_iter(start_height=0):
            block = builder.db.read_block(blockhash)
            fp.write(b64encode(pickle.dumps(block))+b'\n')
    logging.info("create new bootstrap.dat!")


def load_bootstrap_file():
    boot_path = os.path.join(V.DB_HOME_DIR, 'bootstrap.dat')
    with open(boot_path, mode='br') as fp:
        b_data = fp.readline()
        block = None
        while b_data:
            block = pickle.loads(b64decode(b_data.rstrip()))
            for tx in block.txs:
                tx.height = None
                if tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD):
                    continue
                tx_builder.put_unconfirmed(tx)
            for tx in block.txs:
                tx.height = block.height
            new_insert_block(block=block, time_check=False)
            b_data = fp.readline()
    logging.debug("load bootstrap.dat! last={}".format(block))
