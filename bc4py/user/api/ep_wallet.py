from bc4py.config import C, V
from bc4py.bip32 import Bip32, BIP32_HARDEN, get_address
from bc4py.database.create import create_db
from bc4py.database.account import *
from bc4py.user.api.utils import error_response
from fastapi.utils import BaseModel
from bc4py_extension import PyAddress
from multi_party_schnorr import PyKeyPair
from mnemonic import Mnemonic
from binascii import a2b_hex
from logging import getLogger
import asyncio

log = getLogger('bc4py')

language = 'english'
length_list = [128, 160, 192, 224, 256]
loop = asyncio.get_event_loop()


class WalletFormat(BaseModel):
    passphrase: str = ''
    length: int = 256


class PrivateKeyFormat(BaseModel):
    private_key: str
    address: str
    account: str = C.account2name[C.ANT_UNKNOWN]


async def new_address(account: str = C.account2name[C.ANT_UNKNOWN], newly: bool = False):
    """
    This end-point create new address.
    * Arguments
        1. **account** : account name default="@Unknown"
        2. **newly** : create a new address that is not generated yet
    """
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        user_id = await read_name2userid(account, cur)
        addr = None

        if not newly:
            addr = await read_unused_address(user_id, False, cur)

        if addr is None:
            newly = True
            addr = await generate_new_address_by_userid(user_id, cur)

        await db.commit()
    return {
        'account': account,
        'user_id': user_id,
        'address': addr.string,
        'version': addr.version,
        'identifier': addr.identifier().hex(),
        'newly': newly
    }


async def get_keypair(address: str):
    """
    This end-point show keypair info of address.
    * Arguments
        1. **address** : (string, required)
    """
    try:
        async with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = await db.cursor()
            uuid, keypair, path = await read_address2keypair(PyAddress.from_string(address), cur)
            return {
                'uuid': uuid,
                'address': address,
                'private_key': keypair.get_secret_key().hex(),
                'public_key': keypair.get_public_key().hex(),
                'path': path
            }
    except Exception:
        return error_response()


async def create_wallet(wallet: WalletFormat):
    """
    This end-point generate new keystone.json data.
    * Arguments
        1. **passphrase** :  (string, optional, default="")  encrypt passphrase
        2. **strength** :    (numeric, optional, default=256) entropy bit length (12, 15, 18, 21, 24)
    """
    try:
        if wallet.length not in length_list:
            return error_response('length is {}'.format(length_list))
        mnemonic = Mnemonic(language).generate(wallet.length)
        seed = Mnemonic.to_seed(mnemonic, wallet.passphrase)
        root = Bip32.from_entropy(seed)
        bip = root.child_key(44 + BIP32_HARDEN).child_key(C.BIP44_COIN_TYPE)
        # keystone.json format
        return {
            'mnemonic': mnemonic,
            'passphrase': wallet.passphrase,
            'account_secret_key': bip.extended_key(True),
            'account_public_key': bip.extended_key(False),
            'path': bip.path,
            'comment': 'You must recode "mnemonic" and "passphrase" and remove after. '
                       'You can remove "account_secret_key" but you cannot sign and create new account',
        }
    except Exception:
        return error_response()


async def import_private_key(key: PrivateKeyFormat):
    """
    This end-point import privateKey by manual.
    * Arguments
        1. **private_key** : (hex string, required)
        2. **address** :     (string, required) check by this
        3. **account** :     (string, optional, default="@Unknown") insert to account
    """
    try:
        sk = a2b_hex(key.private_key)
        ck = PyAddress.from_string(key.address)
        keypair: PyKeyPair = PyKeyPair.from_secret_key(sk)
        check_ck = get_address(pk=keypair.get_public_key(), hrp=V.BECH32_HRP, ver=C.ADDR_NORMAL_VER)
        if ck != check_ck:
            return error_response('Don\'t match, {}!={}'.format(ck, check_ck))
        async with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = await db.cursor()
            user = await read_name2userid(name=key.account, cur=cur)
            await insert_keypair_from_outside(sk=sk, ck=ck, user=user, cur=cur)
            await db.commit()
        return {'status': True}
    except Exception:
        return error_response()


__all__ = [
    "new_address",
    "get_keypair",
    "create_wallet",
    "import_private_key",
]
