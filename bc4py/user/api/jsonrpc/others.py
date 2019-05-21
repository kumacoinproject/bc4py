from bc4py import __version__, __chain_version__, __message__
from bc4py.config import V
from bc4py.utils import GompertzCurve
from bc4py.bip32 import is_address
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
    users = user_account.get_balance(confirm=6)
    return {
        "version": __version__,
        "protocolversion": __chain_version__,
        "balance": round(users.get(0, 0) / pow(10, V.COIN_DIGIT), 8),
        "blocks": best_block.height,
        "moneysupply": GompertzCurve.calc_total_supply(best_block.height),
        "connections": len(V.PC_OBJ.p2p.user),
        "testnet": V.BECH32_HRP == 'test',
        "difficulty": round(difficulty, 8),
        "paytxfee": round(V.COIN_MINIMUM_PRICE / pow(10, V.COIN_DIGIT), 8),
        "errors": __message__,
    }


async def validateaddress(*args, **kwargs):
    """
    method "validateaddress"
    """
    if len(args) == 0:
        raise ValueError('no argument found')
    address = args[0]
    return {
        "isvalid": is_address(address, V.BECH32_HRP, 0),
        "address": address}


__all__ = [
    "getinfo",
    "validateaddress",
]
