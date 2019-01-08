from bc4py.config import C, V
from bc4py.user.api import web_base
from mnemonic import Mnemonic
from bip32nem import BIP32Key, BIP32_HARDEN
import asyncio
import logging


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
    logging.info("Wallet secret kwy deleted manually.")
    return web_base.json_res({'status': True})


async def unlock_wallet(request):
    async def timeout_now():
        await asyncio.sleep(timeout)
        V.BIP44_BRANCH_SEC_KEY = None
        logging.info("Wallet secret kwy deleted now.")

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
        bip = BIP32Key.fromEntropy(entropy=seed)
        if V.BIP44_ROOT_PUB_KEY != bip.ExtendedKey(private=False):
            return web_base.error_res(errors='Not correct passphrase or rootPublicKey.')
        if timeout > 0:
            asyncio.run_coroutine_threadsafe(coro=timeout_now(), loop=loop)
        else:
            logging.warning("Unlock wallet until system restart.")
        # m/44' / coin_type' / account' / change / address_index
        V.BIP44_BRANCH_SEC_KEY = bip\
            .ChildKey(44 + BIP32_HARDEN)\
            .ChildKey(C.BIP44_COIN_TYPE + BIP32_HARDEN)\
            .ExtendedKey(private=True)
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
        bip = BIP32Key.fromEntropy(seed)
        pri = bip.ExtendedKey(private=True)
        pub = bip.ExtendedKey(private=False)
        return web_base.json_res({
            'mnemonic': mnemonic, 'encrypted': bool(passphrase),
            'private_key': pri, 'public_key': pub})
    except Exception:
        return web_base.error_res()


__all__ = [
    "lock_wallet",
    "unlock_wallet",
    "create_wallet"
]
