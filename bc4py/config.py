from rx.subjects import Subject
from concurrent.futures import ProcessPoolExecutor
from threading import Lock
import atexit
import psutil

# internal stream by ReactiveX
# doc: https://github.com/ReactiveX/RxPY/blob/develop/notebooks/Getting%20Started.ipynb
stream = Subject()
atexit.register(stream.dispose)

# multiprocessing executor
max_process_num = 4
logical_cpu_num = psutil.cpu_count(logical=True) or max_process_num
physical_cpu_nam = psutil.cpu_count(logical=False) or max_process_num
max_workers = min(logical_cpu_num, physical_cpu_nam)
executor = ProcessPoolExecutor(max_workers=max_workers)
atexit.register(executor.shutdown, wait=True)

# executor "submit+add_callback_done" lock
executor_lock = Lock()


class C:  # Constant
    # base currency info
    BASE_CURRENCY = {
        'name': 'PyCoin',
        'unit': 'PC',
        'digit': 8,
        'address': 'NDUMMYADDRESSAAAAAAAAAAAAAAAAAAAACRSTTMF',
        'description': 'Base currency.',
        'image': None
    }

    # consensus
    BLOCK_GENESIS = 0
    BLOCK_COIN_POS = 1
    BLOCK_CAP_POS = 2  # proof of capacity
    BLOCK_FLK_POS = 3  # proof of fund-lock

    BLOCK_YES_POW = 5
    BLOCK_X11_POW = 6
    BLOCK_HMQ_POW = 7
    BLOCK_LTC_POW = 8
    BLOCK_X16R_POW = 9
    consensus2name = {
        BLOCK_GENESIS: 'GENESIS',
        BLOCK_COIN_POS: 'POS_COIN',
        BLOCK_CAP_POS: 'POS_CAP',
        BLOCK_FLK_POS: 'POS_FLK',
        BLOCK_YES_POW: 'POW_YES',
        BLOCK_X11_POW: 'POW_X11',
        BLOCK_HMQ_POW: 'POW_HMQ',
        BLOCK_LTC_POW: 'POW_LTC',
        BLOCK_X16R_POW: 'POW_X16R',
    }

    # tx type
    TX_GENESIS = 0  # Height0の初期設定TX
    TX_POW_REWARD = 1  # POWの報酬TX
    TX_POS_REWARD = 2  # POSの報酬TX
    TX_TRANSFER = 3  # 送受金
    TX_MINT_COIN = 4  # 新規貨幣を鋳造
    TX_VALIDATOR_EDIT = 8  # change validator info
    TX_CONCLUDE_CONTRACT = 9  # conclude static contract tx
    TX_INNER = 255  # 内部のみで扱うTX
    txtype2name = {
        TX_GENESIS: 'GENESIS',
        TX_POW_REWARD: 'POW_REWARD',
        TX_POS_REWARD: 'POS_REWARD',
        TX_TRANSFER: 'TRANSFER',
        TX_MINT_COIN: 'MINT_COIN',
        TX_VALIDATOR_EDIT: 'VALIDATOR_EDIT',
        TX_CONCLUDE_CONTRACT: 'CONCLUDE_CONTRACT',
        TX_INNER: 'TX_INNER'
    }

    # message format
    MSG_NONE = 0  # no message
    MSG_PLAIN = 1  # 明示的にunicode
    MSG_BYTE = 2  # 明示的にbinary
    MSG_MSGPACK = 3  # msgpack protocol
    MSG_HASHLOCKED = 4  # hash-locked transaction
    msg_type2name = {
        MSG_NONE: 'NONE',
        MSG_PLAIN: 'PLAIN',
        MSG_BYTE: 'BYTE',
        MSG_MSGPACK: 'MSGPACK',
        MSG_HASHLOCKED: 'HASHLOCKED'
    }

    # difficulty
    DIFF_RETARGET = 20  # difficultyの計算Block数

    # BIP32
    BIP44_COIN_TYPE = 0x800002aa

    # block params
    MATURE_HEIGHT = 20  # 採掘されたBlockのOutputsが成熟する期間

    # account
    ANT_UNKNOWN = 0  # Unknown user
    ANT_VALIDATOR = 1  # ValidatorAddress
    ANT_CONTRACT = 2  # ContractAddress
    ANT_MINING = 3  # MiningAddress
    account2name = {
        ANT_UNKNOWN: '@Unknown',
        ANT_VALIDATOR: '@Validator',
        ANT_CONTRACT: '@Contract',
        ANT_MINING: '@Mining'
    }

    # Block/TX/Fee limit
    ACCEPT_MARGIN_TIME = 120  # 新規データ受け入れ時間マージンSec
    SIZE_BLOCK_LIMIT = 300 * 1000  # 300kb block
    SIZE_TX_LIMIT = 100 * 1000  # 100kb tx
    CASHE_LIMIT = 300  # Memoryに置く最大Block数、実質Reorg制限
    BATCH_SIZE = 30
    MINTCOIN_GAS = int(10 * pow(10, 6))  # 新規Mintcoin発行GasFee
    SIGNATURE_GAS = int(0.01 * pow(10, 6))  # gas per one signature
    # CONTRACT_CREATE_FEE = int(10 * pow(10, 6))  # コントラクト作成GasFee
    VALIDATOR_EDIT_GAS = int(10 * pow(10, 6))  # gas
    CONTRACT_MINIMUM_INPUT = int(1 * pow(10, 8))  # Contractの発火最小amount


class V:
    # Blockchain basic params
    GENESIS_BLOCK = None
    GENESIS_PARAMS = None
    BLOCK_PREFIX = None
    BLOCK_VALIDATOR_PREFIX = None
    BLOCK_CONTRACT_PREFIX = None
    BLOCK_GENESIS_TIME = None
    BLOCK_TIME_SPAN = None
    BLOCK_MINING_SUPPLY = None
    BLOCK_REWARD = None
    BLOCK_BASE_CONSENSUS = None
    BLOCK_CONSENSUSES = None

    # base coin
    COIN_DIGIT = None
    COIN_MINIMUM_PRICE = None  # Gasの最小Price

    # database path
    DB_HOME_DIR = None
    DB_ACCOUNT_PATH = None

    # Wallet
    # mnemonic =(decrypt)=> seed ==> 44' => coinType' => secret key
    BIP44_ENCRYPTED_MNEMONIC = None
    BIP44_ROOT_PUB_KEY = None  # path: m
    BIP44_BRANCH_SEC_KEY = None  # path: m/44'/coin_type'

    # mining
    MINING_ADDRESS = None
    PC_OBJ = None
    API_OBJ = None

    # developer
    BRANCH_NAME = None


class P:  # 起動中もダイナミックに変化
    F_STOP = False  # Stop signal
    F_NOW_BOOTING = True  # Booting mode flag


class Debug:
    F_SHOW_DIFFICULTY = False
    F_CONSTANT_DIFF = False
    F_STICKY_TX_REJECTION = True


class BlockChainError(Exception):
    pass


__all__ = [
    'stream',
    'max_workers',
    'executor',
    'executor_lock',
    'C',
    'V',
    'P',
    'Debug',
    'BlockChainError',
]

