from bc4py.config import C, V
from bc4py.database.create import closing, create_db
from bc4py.database.account import read_address2keypair
from nem_ed25519.signature import sign
from mnemonic import Mnemonic
from bip32nem import BIP32Key, BIP32_HARDEN
from threading import Timer
import logging
import json
import os.path


def message2signature(raw, address):
    # sign by address
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        uuid, sk, pk = read_address2keypair(address, cur)
    return pk, sign(msg=raw, sk=sk, pk=pk)


def import_keystone(passphrase='', timeout=-1, auto_create=True, language='english'):
    def timeout_now():
        V.BIP44_BRANCH_SEC_KEY = None
        logging.info("Wallet secret kwy deleted now.")
    if V.BIP44_ENCRYPTED_MNEMONIC:
        raise Exception('Already imported, BIP32_ENCRYPTED_MNEMONIC.')
    if V.BIP44_ROOT_PUB_KEY:
        raise Exception('Already imported, BIP32_ROOT_PUBLIC_KEY.')
    keystone_path = os.path.join(V.DB_HOME_DIR, 'keystone.json')
    # params
    try:
        with open(keystone_path, mode='r') as fp:
            wallet = json.load(fp)
        pub = str(wallet['public_key'])
        mnemonic = str(wallet['mnemonic'])
        passphrase = str(wallet.get('passphrase', passphrase))
        timeout = int(wallet.get('timeout', timeout))
        seed = Mnemonic.to_seed(mnemonic, passphrase)
        bip = BIP32Key.fromEntropy(entropy=seed)
        if pub != bip.ExtendedKey(private=False):
            raise Exception('Don\'t match with public key.')
    except FileNotFoundError:
        if not auto_create:
            raise Exception('Cannot load wallet info from {}'.format(keystone_path))
        mnemonic = Mnemonic(language).generate()
        seed = Mnemonic.to_seed(mnemonic, passphrase)
        bip = BIP32Key.fromEntropy(seed)
        pub = bip.ExtendedKey(private=False)
        wallet = {
            'public_key': pub,
            'mnemonic': mnemonic,
            'passphrase': passphrase,
            'timeout': timeout}
        with open(keystone_path, mode='w') as fp:
            json.dump(wallet, fp, indent=4)
        logging.info('Auto create wallet.')
    V.BIP44_ENCRYPTED_MNEMONIC = mnemonic
    V.BIP44_ROOT_PUB_KEY = pub
    # m/44' / coin_type' / account' / change / address_index
    V.BIP44_BRANCH_SEC_KEY = bip \
        .ChildKey(44 + BIP32_HARDEN) \
        .ChildKey(C.BIP44_COIN_TYPE + BIP32_HARDEN) \
        .ExtendedKey(private=True)
    if timeout > 0:
        Timer(timeout, function=timeout_now).start()
    else:
        logging.info("Unlock wallet until system restart.")


def extract_keypair(user, is_inner, index):
    # change: 0=outer、1=inner
    assert isinstance(user, int) and isinstance(is_inner, bool), 'user={}, is_inner={}'.format(user, is_inner)
    if V.BIP44_BRANCH_SEC_KEY is None:
        raise PermissionError('wallet is locked!')
    bip = BIP32Key.fromExtendedKey(V.BIP44_BRANCH_SEC_KEY)
    account = bip.ChildKey(user+BIP32_HARDEN).ChildKey(int(is_inner)).ChildKey(index)
    sk = account.PrivateKey()
    pk, ck = account.NemKeypair(prefix=V.BLOCK_PREFIX)
    return sk, pk, ck


__all__ = [
    "message2signature",
    "import_keystone",
    "extract_keypair",
]
