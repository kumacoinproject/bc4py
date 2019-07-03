from bc4py import __version__, __chain_version__, __message__
from bc4py.config import C, V
from bc4py.utils import GompertzCurve
from bc4py.bip32 import is_address
from bc4py.database.create import create_db
from bc4py.database.account import read_address2userid, read_userid2name, read_address2keypair
from bc4py.database.builder import chain_builder, user_account
from bc4py.chain.difficulty import get_bits_by_hash
from logging import getLogger


log = getLogger('bc4py')


async def getinfo(*args, **kwargs):
    """
    method "getinfo"
    """
    consensus = int(kwargs['password'])
    best_block = chain_builder.best_block
    # difficulty
    bits, target = get_bits_by_hash(previous_hash=best_block.hash, consensus=consensus)
    difficulty = (0xffffffffffffffff // target) / 100000000
    # balance
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        users = await user_account.get_balance(cur=cur, confirm=6)
    return {
        "version": __version__,
        "protocolversion": __chain_version__,
        "balance": round(users.get(0, 0) / pow(10, V.COIN_DIGIT), 8),
        "blocks": best_block.height,
        "moneysupply": GompertzCurve.calc_total_supply(best_block.height),
        "connections": len(V.P2P_OBJ.core.user),
        "testnet": V.BECH32_HRP == 'test',
        "difficulty": round(difficulty, 8),
        "paytxfee": round(V.COIN_MINIMUM_PRICE / pow(10, V.COIN_DIGIT), 8),
        "errors": __message__,
    }


async def validateaddress(*args, **kwargs):
    """
    Arguments:
        1. "address"     (string, required) The bitcoin address to validate

    Result:
        {
          "isvalid" : true|false,       (boolean) If the address is valid or not. If not, this is the only property returned.
          "address" : "address",        (string) The bitcoin address validated
          "ismine" : true|false,        (boolean) If the address is yours or not
          "pubkey" : "publickeyhex",    (string, optional) The hex value of the raw public key, for single-key addresses (possibly embedded in P2SH or P2WSH)
          "account" : "account"         (string) DEPRECATED. The account associated with the address, "" is the default account
          "hdkeypath" : "keypath"       (string, optional) The HD keypath if the key is HD and available
        }
    """
    if len(args) == 0:
        raise ValueError('no argument found')
    address = args[0]
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        user_id = await read_address2userid(address=address, cur=cur)
        if user_id is None:
            return {
                "isvalid": is_address(address, V.BECH32_HRP, 0),
                "address": address,
                "ismine": False,
                "pubkey": None,
                "account": None,
                "hdkeypath": None,
            }
        else:
            account = await read_userid2name(user=user_id, cur=cur)
            account = "" if account == C.ANT_UNKNOWN else account
            _, keypair, path = await read_address2keypair(address=address, cur=cur)
            return {
                "isvalid": is_address(address, V.BECH32_HRP, 0),
                "address": address,
                "ismine": True,
                "pubkey": keypair.get_public_key().hex(),
                "account": account,
                "hdkeypath": path,
            }


__all__ = [
    "getinfo",
    "validateaddress",
]
