from bc4py.config import C, V
from bc4py.bip32 import Bip32, BIP32_HARDEN, get_address
from bc4py.user.api import utils
from bc4py.database.create import create_db
from bc4py.database.account import insert_keypair_from_outside, read_name2userid
from multi_party_schnorr import PyKeyPair
from mnemonic import Mnemonic
from binascii import a2b_hex
import asyncio
from logging import getLogger

log = getLogger('bc4py')

language = 'english'
length_list = [128, 160, 192, 224, 256]
loop = asyncio.get_event_loop()


async def create_wallet(request):
    try:
        post = await utils.content_type_json_check(request)
        passphrase = str(post.get('passphrase', ''))
        length = int(post.get('length', 256))
        if length not in length_list:
            return utils.error_res('length is {}'.format(length_list))
        mnemonic = Mnemonic(language).generate(length)
        seed = Mnemonic.to_seed(mnemonic, passphrase)
        root = Bip32.from_entropy(seed)
        bip = root.child_key(44 + BIP32_HARDEN).child_key(C.BIP44_COIN_TYPE)
        # keystone.json format
        return utils.json_res({
            'mnemonic': mnemonic,
            'passphrase': passphrase,
            'account_secret_key': bip.extended_key(True),
            'account_public_key': bip.extended_key(False),
            'path': bip.path,
            'comment': 'You must recode "mnemonic" and "passphrase" and remove after. '
                       'You can remove "account_secret_key" but you cannot sign and create new account',
        })
    except Exception:
        return utils.error_res()


async def import_private_key(request):
    try:
        post = await utils.content_type_json_check(request)
        sk = a2b_hex(post['private_key'])
        ck = post['address']
        name = post.get('account', C.account2name[C.ANT_UNKNOWN])
        keypair: PyKeyPair = PyKeyPair.from_secret_key(sk)
        check_ck = get_address(pk=keypair.get_public_key(), hrp=V.BECH32_HRP, ver=C.ADDR_NORMAL_VER)
        if ck != check_ck:
            return utils.error_res('Don\'t match, {}!={}'.format(ck, check_ck))
        with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = db.cursor()
            user = read_name2userid(name=name, cur=cur)
            insert_keypair_from_outside(sk=sk, ck=ck, user=user, cur=cur)
            db.commit()
        return utils.json_res({'status': True})
    except Exception:
        return utils.error_res()


__all__ = [
    "create_wallet",
    "import_private_key",
]
