from bc4py import __chain_version__
from bc4py.config import C, V
from bc4py.chain import msgpack
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.bip32 import Bip32, BIP32_HARDEN
from bc4py.chain.checking import new_insert_block
from random import randint
from binascii import a2b_hex
from mnemonic import Mnemonic
from time import time
from logging import getLogger
import requests
import msgpack as original_mpk
import json
import gzip
import os

log = getLogger('bc4py')
language = 'english'


def create_boot_file(genesis_block, params, network_ver=None, connections=()):
    network_ver = network_ver or randint(0x0, 0xffffffff)
    assert isinstance(network_ver, int) and 0x0 <= network_ver <= 0xffffffff
    data = {
        'genesis_hash': genesis_block.hash.hex(),
        'genesis_binary': genesis_block.b.hex(),
        'txs': [{
            'hash': tx.hash.hex(),
            'binary': tx.b.hex()
        } for tx in genesis_block.txs],
        'connections': connections,
        'network_ver': network_ver,
        'params': params,
    }
    boot_path = os.path.join(V.DB_HOME_DIR, 'boot.json')
    with open(boot_path, mode='w') as fp:
        json.dump(data, fp, indent=4)
    log.info("create new boot.json!")


def load_boot_file(url=None):
    normal_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'boot.json')
    extra_path = os.path.join(V.DB_HOME_DIR, 'boot.json')
    if url:
        data = requests.get(url=url).json()
    elif os.path.exists(normal_path):
        with open(normal_path, mode='r') as fp:
            data = json.load(fp)
    elif os.path.exists(extra_path):
        with open(extra_path, mode='r') as fp:
            data = json.load(fp)
    else:
        raise FileNotFoundError('Cannot find boot.json "{}" or "{}" ?'.format(normal_path, extra_path))
    # load from exist boot.json
    genesis_block = Block.from_binary(binary=a2b_hex(data['genesis_binary']))
    assert genesis_block.hash == a2b_hex(data['genesis_hash'])
    genesis_block.flag = C.BLOCK_GENESIS
    genesis_block.height = 0
    for tx_dct in data['txs']:
        tx = TX.from_binary(binary=a2b_hex(tx_dct['binary']))
        assert tx.hash == a2b_hex(tx_dct['hash'])
        tx.height = 0
        genesis_block.txs.append(tx)
    connections = data['connections']
    network_ver = data['network_ver']
    if isinstance(data['params'], dict):
        # new type boot.json
        params = data['params']
        params['consensus'] = {int(k): v for k, v in params['consensus'].items()}
    elif isinstance(data['params'], str):
        # old type boot.json
        params = original_mpk.unpackb(a2b_hex(data['params']), raw=True, encoding='utf8')
    else:
        raise Exception('Unknown type params')
    return genesis_block, params, network_ver, connections


def load_bootstrap_file(boot_path=None):
    boot_path = boot_path or os.path.join(V.DB_HOME_DIR, 'bootstrap-ver{}.dat.gz'.format(__chain_version__))
    if not os.path.exists(boot_path):
        log.warning("Not found, skip import bootstrap.dat.gz")
        return
    log.info("Start to load blocks from bootstrap.dat.gz")
    s = time()
    with gzip.open(boot_path, mode='rb') as fp:
        block = None
        for block, work_hash, _bias in msgpack.stream_unpacker(fp):
            block.work_hash = work_hash
            block._bias = _bias
            for tx in block.txs:
                tx.height = block.height
            new_insert_block(block=block, f_time=False, f_sign=True)
            if block.height % 1000 == 0:
                print("Load block now {} height {}Sec".format(block.height, round(time() - s)))
    log.info("load bootstrap.dat.gz finished, last={} {}Minutes".format(block, (time() - s) // 60))


def import_keystone(passphrase='', auto_create=True):
    if V.EXTENDED_KEY_OBJ is not None:
        raise Exception('keystone is already imported')
    keystone_path = os.path.join(V.DB_HOME_DIR, 'keystone.json')
    if os.path.exists(keystone_path):
        # import from keystone file
        bip = load_keystone(keystone_path)
        bip.path = "m/44'/{}'".format(C.BIP44_COIN_TYPE % BIP32_HARDEN)
        log.info("load keystone file {}".format(bip))
    elif auto_create:
        # create keystone file
        bip = create_keystone(passphrase, keystone_path, None)
        log.warning("create keystone file {}".format(bip))
    else:
        raise Exception('Not found keystone file!')
    V.EXTENDED_KEY_OBJ = bip


def load_keystone(keystone_path):
    with open(keystone_path, mode='r') as fp:
        wallet = json.load(fp)
    sec = wallet.get('account_secret_key')
    pub = wallet.get('account_public_key')
    if sec:
        bip = Bip32.from_extended_key(key=sec, is_public=False)
    elif pub:
        bip = Bip32.from_extended_key(key=pub, is_public=True)
    elif 'mnemonic' in wallet and 'passphrase' in wallet:
        # recover from mnemonic
        bip = create_keystone(wallet['passphrase'], keystone_path, wallet['mnemonic'])
    else:
        raise Exception('Cannot find "account_secret_key" and "account_public_key" in keystone')
    return bip


def create_keystone(passphrase, keystone_path, mnemonic):
    if mnemonic is None:
        mnemonic = Mnemonic(language).generate(256)
    seed = Mnemonic.to_seed(mnemonic, passphrase)
    root = Bip32.from_entropy(seed)
    bip = root.child_key(44+BIP32_HARDEN).child_key(C.BIP44_COIN_TYPE)
    wallet = {
        'mnemonic': mnemonic,
        'passphrase': passphrase,
        'account_secret_key': bip.extended_key(True),
        'account_public_key': bip.extended_key(False),
        'path': bip.path,
        'comment': 'You must recode "mnemonic" and "passphrase" and remove after. '
                   'You can remove "account_secret_key" but you cannot sign and create new account.',
    }
    with open(keystone_path, mode='w') as fp:
        json.dump(wallet, fp, indent=4)
    return bip


__all__ = [
    "create_boot_file",
    "load_boot_file",
    "load_bootstrap_file",
    "import_keystone",
]
