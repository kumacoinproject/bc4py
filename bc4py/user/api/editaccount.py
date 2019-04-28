from bc4py.config import C, V
from bc4py.bip32 import Bip32, BIP32_HARDEN, get_address
from bc4py.user.api import web_base
from bc4py.user.tools import repair_wallet
from bc4py.database.create import closing, create_db
from bc4py.database.account import insert_keypair_from_outside, read_name2user
from multi_party_schnorr import PyKeyPair
from mnemonic import Mnemonic
from binascii import a2b_hex
import asyncio
from logging import getLogger

log = getLogger('bc4py')

language = 'english'
words2length = {12: 128, 15: 160, 18: 192, 21: 224, 24: 256}
loop = asyncio.get_event_loop()


async def lock_wallet(request):
    if V.BIP44_ENCRYPTED_MNEMONIC is None:
        return web_base.error_res(errors='Not found BIP32_ENCRYPTED_MNEMONIC.')
    if V.BIP44_ROOT_PUB_KEY is None:
        return web_base.error_res(errors='Not found BIP32_ROOT_PUBLIC_KEY.')
    if V.BIP44_BRANCH_SEC_KEY is None:
        return web_base.error_res(errors='Already locked wallet.')
    V.BIP44_BRANCH_SEC_KEY = None
    log.info("Wallet secret kwy deleted manually.")
    return web_base.json_res({'status': True})


async def unlock_wallet(request):

    async def timeout_now():
        await asyncio.sleep(timeout)
        V.BIP44_BRANCH_SEC_KEY = None
        log.info("deleted wallet secret key now.")

    if V.BIP44_ENCRYPTED_MNEMONIC is None:
        return web_base.error_res(errors='Not found BIP32_ENCRYPTED_MNEMONIC.')
    if V.BIP44_ROOT_PUB_KEY is None:
        return web_base.error_res(errors='Not found BIP32_ROOT_PUBLIC_KEY.')
    if V.BIP44_BRANCH_SEC_KEY:
        return web_base.error_res(errors='Already unlocked wallet.')
    try:
        post = await web_base.content_type_json_check(request)
        passphrase = str(post.get('passphrase', ''))
        timeout = int(post.get('timeout', 60))
        seed = Mnemonic.to_seed(V.BIP44_ENCRYPTED_MNEMONIC, passphrase)
        bip = Bip32.from_entropy(entropy=seed)
        if V.BIP44_ROOT_PUB_KEY != bip.extended_key(is_private=False):
            return web_base.error_res(errors='Not correct passphrase or rootPublicKey.')
        if timeout > 0:
            asyncio.run_coroutine_threadsafe(coro=timeout_now(), loop=loop)
        else:
            log.warning("Unlock wallet until system restart.")
        # m/44' / coin_type' / account' / change / address_index
        V.BIP44_BRANCH_SEC_KEY = bip\
            .child_key(44 + BIP32_HARDEN)\
            .child_key(C.BIP44_COIN_TYPE)\
            .extended_key(is_private=True)
        return web_base.json_res({'status': True, 'timeout': timeout})
    except Exception:
        return web_base.error_res()


async def create_wallet(request):
    try:
        post = await web_base.content_type_json_check(request)
        passphrase = str(post.get('passphrase', ''))
        strength = int(post.get('strength', 12))
        if strength not in words2length:
            return web_base.error_res('not found length in {}'.format(list(words2length.keys())))
        mnemonic = Mnemonic(language).generate(words2length[strength])
        seed = Mnemonic.to_seed(mnemonic, passphrase)
        bip = Bip32.from_entropy(seed)
        pri = bip.extended_key(is_private=True)
        pub = bip.extended_key(is_private=False)
        return web_base.json_res({
            'mnemonic': mnemonic,
            'encrypted': bool(passphrase),
            'private_key': pri,
            'public_key': pub
        })
    except Exception:
        return web_base.error_res()


async def import_private_key(request):
    if V.BIP44_BRANCH_SEC_KEY is None:
        return web_base.error_res('wallet is locked!')
    try:
        post = await web_base.content_type_json_check(request)
        sk = a2b_hex(post['private_key'])
        ck = post['address']
        name = post.get('account', C.account2name[C.ANT_UNKNOWN])
        keypair: PyKeyPair = PyKeyPair.from_secret_key(sk)
        check_ck = get_address(pk=keypair.get_public_key(), prefix=V.BLOCK_PREFIX)
        if ck != check_ck:
            return web_base.error_res('Don\'t match, {}!={}'.format(ck, check_ck))
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            user = read_name2user(name=name, cur=cur)
            insert_keypair_from_outside(sk=sk, ck=ck, user=user, cur=cur)
            db.commit()
        return web_base.json_res({'status': True})
    except Exception:
        return web_base.error_res()


__all__ = [
    "lock_wallet",
    "unlock_wallet",
    "create_wallet",
    "import_private_key",
]
