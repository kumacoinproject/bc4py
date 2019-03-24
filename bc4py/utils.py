from bc4py.config import C, V
from bc4py.gittool import get_current_branch
from bc4py.chain.utils import GompertzCurve
from Cryptodome.Cipher import AES
from Cryptodome import Random
from Cryptodome.Hash import SHA256
from logging import getLogger
import multiprocessing
import os
import psutil
import sys

WALLET_VERSION = 0
log = getLogger('bc4py')


def set_database_path(sub_dir=None):
    V.DB_HOME_DIR = os.path.join(os.path.expanduser("~"), 'blockchain-py')
    if not os.path.exists(V.DB_HOME_DIR):
        os.makedirs(V.DB_HOME_DIR)
    if sub_dir:
        V.DB_HOME_DIR = os.path.join(V.DB_HOME_DIR, sub_dir)
        if not os.path.exists(V.DB_HOME_DIR):
            os.makedirs(V.DB_HOME_DIR)
    V.DB_ACCOUNT_PATH = os.path.join(V.DB_HOME_DIR, 'wallet.ver{}.dat'.format(WALLET_VERSION))


def set_blockchain_params(genesis_block, params):
    assert 'spawn' in multiprocessing.get_all_start_methods(), 'Not found spawn method.'
    V.GENESIS_BLOCK = genesis_block
    V.GENESIS_PARAMS = params
    V.BLOCK_PREFIX = params.get('prefix')
    V.BLOCK_VALIDATOR_PREFIX = params.get('validator_prefix')
    V.BLOCK_CONTRACT_PREFIX = params.get('contract_prefix')
    V.BLOCK_GENESIS_TIME = params.get('genesis_time')
    V.BLOCK_MINING_SUPPLY = params.get('mining_supply')
    V.BLOCK_TIME_SPAN = params.get('block_span')
    V.BLOCK_REWARD = params.get('block_reward')
    V.COIN_DIGIT = params.get('digit_number')
    V.COIN_MINIMUM_PRICE = params.get('minimum_price')
    V.BLOCK_CONSENSUSES = params.get('consensus')
    GompertzCurve.k = V.BLOCK_MINING_SUPPLY
    V.BRANCH_NAME = get_current_branch()


def delete_pid_file():
    # PIDファイルを削除
    pid_path = os.path.join(V.DB_HOME_DIR, 'pid.lock')
    if os.path.exists(pid_path):
        os.remove(pid_path)


def make_pid_file():
    # 既に起動していないかPIDをチェック
    pid_path = os.path.join(V.DB_HOME_DIR, 'pid.lock')
    if os.path.exists(pid_path):
        with open(pid_path, mode='r') as fp:
            pid = int(fp.read())
        if psutil.pid_exists(pid):
            raise RuntimeError('Already running blockchain-py.')
        os.remove(pid_path)
    with open(pid_path, mode='w') as fp:
        fp.write(str(os.getpid()))


class AESCipher:

    @staticmethod
    def create_key():
        return os.urandom(AES.block_size)

    @staticmethod
    def encrypt(key, raw):
        assert isinstance(key, bytes)
        assert isinstance(raw, bytes), "input data is bytes"
        key = SHA256.new(key).digest()[:AES.block_size]
        raw = AESCipher._pad(raw)
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return iv + cipher.encrypt(raw)

    @staticmethod
    def decrypt(key, enc):
        assert isinstance(key, bytes)
        assert isinstance(enc, bytes), 'Encrypt data is bytes'
        key = SHA256.new(key).digest()[:AES.block_size]
        iv = enc[:AES.block_size]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        raw = AESCipher._unpad(cipher.decrypt(enc[AES.block_size:]))
        if len(raw) == 0:
            raise ValueError("AES decryption error, not correct key.")
        else:
            return raw

    @staticmethod
    def _pad(s):
        pad = AES.block_size - len(s) % AES.block_size
        add = AES.block_size - len(s) % AES.block_size
        return s + add * pad.to_bytes(1, 'little')

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s) - 1:])]


class ProgressBar:
    """
    terminal progressbar
    original: https://github.com/bozoh/console_progressbar
    author: Carlos Alexandre S. da Fonseca
    """

    def __init__(self, prefix, default_suffix='', total=100, decimals=0, length=50, fill='X', zfill='-'):
        self.prefix = prefix
        self.default_suffix = default_suffix
        self.__decimals = decimals
        self.__length = length
        self.__fill = fill
        self.__zfill = zfill
        self.__total = total

    def _generate_bar(self, iteration, suffix=None):
        percent = ("{0:." + str(self.__decimals) + "f}")
        percent = percent.format(100 * (iteration / float(self.__total)))
        filled_length = int(self.__length * iteration // self.__total)
        bar = self.__fill * filled_length + self.__zfill * (self.__length - filled_length)
        return '{0} |{1}| {2}% {3}'.format(self.prefix, bar, percent, suffix or self.default_suffix)

    def print_progress_bar(self, iteration, suffix=None):
        print('\r%s' % (self._generate_bar(iteration, suffix)), end='')
        sys.stdout.flush()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.print_progress_bar(self.__total, 'Complete')
            print()
        else:
            print()
            sys.stdout.flush()
            log.error('Error on progress, {}'.format(exc_val))
        return True


__all__ = [
    "set_database_path",
    "set_blockchain_params",
    "delete_pid_file",
    "make_pid_file",
    "AESCipher",
    "ProgressBar",
]
