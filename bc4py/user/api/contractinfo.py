from bc4py.config import C, V, BlockChainError
from bc4py.user import CoinObject
from bc4py.user.api import web_base
from bc4py.database.builder import builder, tx_builder, user_account
from bc4py.database.create import closing, create_db
from bc4py.database.account import *
from bc4py.database.tools import get_unspents_iter
from bc4py.database.validator import get_validator_object
from bc4py.database.contract import get_contract_object
from aiohttp import web
from binascii import hexlify
import logging


async def validator_info(request):
    try:
        c_address = request.query['c_address']
        v = get_validator_object(c_address=c_address)
        return web_base.json_res(v.info)
    except Exception as e:
        logging.error(e)
        return web_base.error_res()


async def contract_info(request):
    try:
        c_address = request.query['c_address']
        c = get_contract_object(c_address=c_address)
        return web_base.json_res(c.info)
    except Exception as e:
        logging.error(e)
        return web_base.error_res()


async def contract_storage(request):
    def decode(b):
        if isinstance(b, bytes) or isinstance(b, bytearray):
            return b.decode(errors='ignore')
        return b
    try:
        c_address = request.query['c_address']
        c = get_contract_object(c_address=c_address)
        storage = {decode(k): decode(v) for k, v in c.storage.items()}
        return web_base.json_res(storage)
    except Exception as e:
        logging.error(e)
        return web_base.error_res()


__all__ = [
    "validator_info",
    "contract_info",
    "contract_storage"
]
