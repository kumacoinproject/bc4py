#!/user/env python3
# -*- coding: utf-8 -*-


import configparser


class C:  # Constant
    # base currency info
    BASE_CURRENCY_NAME = 'PyCoin'
    BASE_CURRENCY_UNIT = 'PC'
    BASE_CURRENCY_DESCRIPTION = 'Base currency.'

    # consensus
    BLOCK_GENESIS = 0
    BLOCK_YES_POW = 1
    BLOCK_POS = 2
    # HYBRID = 3
    BLOCK_X11_POW = 4
    BLOCK_HMQ_POW = 5
    BLOCK_LTC_POW = 6
    BLOCK_X16R_POW = 7
    consensus2name = {0: 'GENESIS', 1: 'POW_YES', 2: 'POS', 4: 'POW_X11', 5: 'POW_HMQ',
                      6: 'POW_LTC', 7: 'POW_X16R'}

    # tx type
    TX_GENESIS = 0  # Height0の初期設定TX
    TX_POW_REWARD = 1  # POWの報酬TX
    TX_POS_REWARD = 2  # POSの報酬TX
    TX_TRANSFER = 3  # 送受金
    TX_MINT_COIN = 4  # 新規貨幣を鋳造
    TX_CREATE_CONTRACT = 5  # コントラクトアドレスを作成
    TX_START_CONTRACT = 6  # コントラクトの開始TX
    TX_FINISH_CONTRACT = 7  # コントラクトの終了TX
    TX_INNER = 255  # 内部のみで扱うTX
    txtype2name = {
        TX_GENESIS: 'GENESIS', TX_POW_REWARD: 'POW_REWARD', TX_POS_REWARD: 'POS_REWARD',
        TX_TRANSFER: 'TRANSFER', TX_MINT_COIN: 'MINT_COIN', TX_CREATE_CONTRACT: 'CREATE_CONTRACT',
        TX_START_CONTRACT: 'START_CONTRACT', TX_FINISH_CONTRACT: 'FINISH_CONTRACT', TX_INNER: 'TX_INNER'}

    # message format
    MSG_NONE = 0  # no message
    MSG_PLAIN = 1  # 明示的にunicode
    MSG_BYTE = 2  # 明示的にbinary
    msg_type2name = {0: 'NONE', 1: 'PLAIN', 2: 'BYTE'}

    # difficulty
    DIFF_RETARGET = 20  # difficultyの計算Block数

    # block params
    MATURE_HEIGHT = 20  # 採掘されたBlockのOutputsが成熟する期間
    CHECKPOINT_SPAN = 200  # checkpointの作成間隔

    # account
    ANT_RESERVED = 0  # 未使用
    ANT_UNKNOWN = 1  # 使用済みだがTag無し
    ANT_OUTSIDE = 2  # 外部への入出金
    ANT_CONTRACT = 3  # コントラクトアドレス
    # name
    ANT_NAME_RESERVED = '@Reserved'
    ANT_NAME_UNKNOWN = '@Unknown'
    ANT_NAME_OUTSIDE = '@Outside'
    ANT_NAME_CONTRACT = '@Contract'

    # Block/TX/Fee limit
    ACCEPT_MARGIN_TIME = 120  # 新規データ受け入れ時間マージンSec
    SIZE_BLOCK_LIMIT = 300*1000  # 300kb block
    SIZE_TX_LIMIT = 100*1000  # 100kb tx
    CASHE_LIMIT = 100  # Memoryに置く最大Block数、実質Reorg制限
    BATCH_SIZE = 10
    MINTCOIN_FEE = 10 * 1000000  # 新規Mintcoin発行GasFee
    CONTRACT_CREATE_FEE = 10 * 1000000  # コントラクト作成GasFee


class V:  # 起動時に設定される変数
    # BLock params
    BLOCK_GENESIS_HASH = None
    BLOCK_PREFIX = None
    BLOCK_CONTRACT_PREFIX = None
    BLOCK_GENESIS_TIME = None
    BLOCK_TIME_SPAN = None
    BLOCK_ALL_SUPPLY = None
    BLOCK_REWARD = None
    BLOCK_BASE_CONSENSUS = None
    BLOCK_CONSENSUSES = None

    # base coin
    COIN_DIGIT = None
    COIN_MINIMUM_PRICE = None  # Gasの最小Price
    CONTRACT_MINIMUM_AMOUNT = None
    CONTRACT_VALIDATOR_ADDRESS = None

    # database path
    SUB_DIR = None
    DB_HOME_DIR = None
    DB_ACCOUNT_PATH = None

    # encryption key
    ENCRYPT_KEY = None

    # mining
    MINING_ADDRESS = None
    MINING_MESSAGE = None
    PC_OBJ = None
    API_OBJ = None


class P:  # 起動中もダイナミックに変化
    VALIDATOR_OBJ = None  # Validation request
    F_NOW_BOOTING = True  # Booting mode flag
    NEW_CHAIN_INFO_QUE = None  # API streaming


class Debug:
    F_WS_FULL_ERROR_MSG = False
    F_LIMIT_INCLUDE_TX_IN_BLOCK = 0  # 1blockに入れるTXの最大数(0=無効)
    F_MINING_POWER_SAVE = 0.0
    F_SHOW_DIFFICULTY = False
    F_CONSTANT_DIFF = False
    F_STICKY_TX_REJECTION = True


class MyConfigParser(configparser.ConfigParser):
    """
    config = MyConfigParser()
    config.param('section', 'name', str, 'Bob')
    config.param('section', 'number', int, 3)
    """
    def __init__(self, file='./config.ini'):
        super(MyConfigParser, self).__init__()
        self.file = file
        try:
            self.read(file, 'UTF-8')
        except UnicodeEncodeError:
            self.read(file)
        except FileNotFoundError:
            pass

    def __repr__(self):
        config = ""
        for k, v in self._sections.items():
            config += "[{}]\n".format(k)
            for _k, _v in v.items():
                config += "{}={}\n".format(_k, _v)
        return config

    def _write_file(self):
        with open(self.file, mode='w') as fp:
            self.write(fp)

    def param(self, section, name, dtype=str, default=None):
        try:
            if dtype is bool:
                data = self.getboolean(section, name)
            elif dtype is int:
                data = self.getint(section, name)
            elif dtype is float:
                data = self.getfloat(section, name)
            elif dtype is str:
                data = self.get(section, name)
            else:
                raise configparser.Error('Not found type {}'.format(type(dtype)))
        except ValueError:
            return default
        except configparser.NoSectionError:
            data = default
            self.add_section(section)
            self.set(section, name, str(data))
            self._write_file()
        except configparser.NoOptionError:
            data = default
            self.set(section, name, str(data))
            self._write_file()
        return data


class BlockChainError(Exception):
    pass
