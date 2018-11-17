from bc4py.user.api import web_base
from bc4py.database.builder import builder
from bc4py.database.validator import get_validator_object
from bc4py.database.contract import get_contract_object
import logging


async def contract_info(request):
    try:
        c_address = request.query['c_address']
        f_confirmed = bool(request.query.get('confirmed', False))
        best_block = builder.best_block if f_confirmed else None
        c = get_contract_object(c_address=c_address, best_block=best_block)
        return web_base.json_res(c.info)
    except Exception as e:
        logging.error(e)
        return web_base.error_res()


async def validator_info(request):
    try:
        c_address = request.query['c_address']
        f_confirmed = bool(request.query.get('confirmed', False))
        best_block = builder.best_block if f_confirmed else None
        v = get_validator_object(c_address=c_address, best_block=best_block)
        return web_base.json_res(v.info)
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
        f_confirmed = bool(request.query.get('confirmed', False))
        best_block = builder.best_block if f_confirmed else None
        c = get_contract_object(c_address=c_address, best_block=best_block)
        if c is None:
            return web_base.json_res({})
        storage = {decode(k): decode(v) for k, v in c.storage.items()}
        return web_base.json_res(storage)
    except Exception as e:
        logging.error(e)
        return web_base.error_res()


__all__ = [
    "contract_info",
    "validator_info",
    "contract_storage"
]
