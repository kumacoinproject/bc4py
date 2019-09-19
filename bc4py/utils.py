from bc4py.config import C, V
from bc4py.gittool import get_current_branch, calc_python_source_hash
from bc4py.chain.utils import GompertzCurve
from Cryptodome.Cipher import AES
from Cryptodome import Random
from Cryptodome.Hash import SHA256
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from logging import getLogger, DEBUG, INFO, WARNING, ERROR
import multiprocessing
import os
import psutil
import sys

WALLET_VERSION = 0
log = getLogger('bc4py')
NAME2LEVEL = {
    'DEBUG': DEBUG,
    'INFO': INFO,
    'WARNING': WARNING,
    'ERROR': ERROR,
}


def set_database_path(sub_dir=None):
    """setup database/wallet path"""
    # DB_HOME_DIR = home/blockchain-py
    if V.DB_HOME_DIR is None:
        V.DB_HOME_DIR = os.path.join(os.path.expanduser("~"), 'blockchain-py')
    assert V.DB_HOME_DIR is not None

    # create DB_HOME_DIR
    if not os.path.exists(V.DB_HOME_DIR):
        os.makedirs(V.DB_HOME_DIR)

    if sub_dir:
        # DB_HOME_DIR = home/blockchain-py/sub_dir
        V.DB_HOME_DIR = os.path.join(V.DB_HOME_DIR, sub_dir)
        if not os.path.exists(V.DB_HOME_DIR):
            os.makedirs(V.DB_HOME_DIR)

    # DB_ACCOUNT_PATH = DB_HOME_DIR/wallet.dat
    if V.DB_ACCOUNT_PATH is None:
        V.DB_ACCOUNT_PATH = os.path.join(V.DB_HOME_DIR, 'wallet.ver{}.dat'.format(WALLET_VERSION))
    assert V.DB_ACCOUNT_PATH is not None


def set_blockchain_params(genesis_block, params):
    assert 'spawn' in multiprocessing.get_all_start_methods(), 'Not found spawn method'
    V.GENESIS_BLOCK = genesis_block
    V.GENESIS_PARAMS = params
    V.BECH32_HRP = params.get('hrp')
    V.BLOCK_GENESIS_TIME = params.get('genesis_time')
    V.BLOCK_MINING_SUPPLY = params.get('mining_supply')
    V.BLOCK_TIME_SPAN = params.get('block_span')
    V.BLOCK_REWARD = params.get('block_reward')
    V.COIN_DIGIT = params.get('digit_number')
    V.COIN_MINIMUM_PRICE = params.get('minimum_price')
    V.BLOCK_CONSENSUSES = params.get('consensus')
    GompertzCurve.k = V.BLOCK_MINING_SUPPLY
    V.SOURCE_HASH = calc_python_source_hash()
    V.BRANCH_NAME = get_current_branch()


def check_already_started():
    assert V.DB_HOME_DIR is not None
    # check already started
    pid_path = os.path.join(V.DB_HOME_DIR, 'pid.lock')
    if os.path.exists(pid_path):
        with open(pid_path, mode='r') as fp:
            pid = int(fp.read())
        try:
            if psutil.pid_exists(pid):
                if 'python' in psutil.Process(pid).exe():
                    raise RuntimeError('Already running bc4py pid={}'.format(pid))
        except Exception as e:
            log.fatal(f"psutil exception '{e}', check pid and remove pid.lock if you think no problem")
            exit(1)
    new_pid = os.getpid()
    with open(pid_path, mode='w') as fp:
        fp.write(str(new_pid))
    log.info("create new process lock file pid={}".format(new_pid))


def console_args_parser():
    """get help by `python publicnode.py -h`"""
    p = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    p.add_argument('--p2p',
                   help='p2p server bind port',
                   default=2000,
                   type=int)
    p.add_argument('--rest',
                   help='REST API bind port',
                   default=3000,
                   type=int)
    p.add_argument('--host',
                   help='REST API bind host',
                   default='127.0.0.1',
                   type=str)
    p.add_argument('--user', '-u',
                   help='API username, auto generate if null',
                   default=None,
                   type=str)
    p.add_argument('--password', '-p',
                   help='API password, auto generate if null',
                   default=None,
                   type=str)
    p.add_argument('--sub-dir',
                   help='setup blockchain folder path',
                   default=None)
    p.add_argument('--log-level',
                   help='logging level',
                   choices=list(NAME2LEVEL),
                   default='INFO')
    p.add_argument('--log-path',
                   help='recode log file path',
                   default=None,
                   type=str)
    p.add_argument('--remove-log',
                   help='remove old log file when start program',
                   action='store_true')
    p.add_argument('--daemon',
                   help='make process daemon',
                   action='store_true')
    p.add_argument('--staking',
                   help='enable coin base staking',
                   action='store_true')
    p.add_argument('--solo-mining',
                   help='solo mining for debug or testnet',
                   action='store_true')
    p.add_argument('--console',
                   help='netcat console monitor',
                   action='store_true')
    p.add_argument('--txindex',
                   help='index tx for `/public/gettxbyhash`',
                   action='store_true')
    p.add_argument('--addrindex',
                   help='index addr for `/public/listunspents`',
                   action='store_true')
    return p.parse_args()


def check_process_status(f_daemon):
    assert sys.version_info.major == 3, 'please use Python3.6+, not Python{}'.format(sys.version_info.major)
    if sys.platform == 'win32':
        # windows
        if f_daemon:
            if sys.executable.endswith("pythonw.exe"):
                sys.stdout = open(os.devnull, "w")
                sys.stderr = open(os.devnull, "w")
            else:
                print("ERROR: Please execute  by `pythonw.exe` not `python.exe` if you enable daemon flag")
                sys.exit()
        else:
            if sys.executable.endswith("pythonw.exe"):
                print("ERROR: Please execute  by `python.exe`")
                sys.exit()
            else:
                # stdin close to prevent lock on console
                sys.stdin.close()
    else:
        # other
        if f_daemon:
            pid = os.fork()
            if pid == 0:
                # child process (daemon)
                sys.stdout = open(os.devnull, "w")
                sys.stderr = open(os.devnull, "w")
            else:
                # main process
                print("INFO: Make daemon process pid={}".format(pid))
                sys.exit()
        else:
            # stdin close to prevent lock on console
            sys.stdin.close()


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
            raise ValueError("AES decryption error, not correct key")
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
    "check_already_started",
    "console_args_parser",
    "check_process_status",
    "AESCipher",
    "ProgressBar",
]
