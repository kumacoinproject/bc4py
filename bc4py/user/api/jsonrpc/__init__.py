from pydantic import BaseModel
from fastapi import Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from .account import *
from .mining import *
from .others import *
from logging import getLogger
import traceback

log = getLogger('bc4py')
security = HTTPBasic()

# about "coinbasetxn"
# https://bitcoin.stackexchange.com/questions/13438/difference-between-coinbaseaux-flags-vs-coinbasetxn-data
# https://github.com/bitcoin/bips/blob/master/bip-0022.mediawiki

"""
JSON-RPC server
It's designed for Yiimp pool program.
"""


class JsonRpcFormat(BaseModel):
    method: str
    params: list = None
    id: str = None


async def json_rpc(data: JsonRpcFormat, credentials: HTTPBasicCredentials = Depends(security)):
    """
    JSON-RPC for Stratum-pool-mining

    BasicAuth params
    * **user**: no meaning
    * **password**: mining consensus number from config.py
    """
    user, password = credentials.username, credentials.password

    try:
        # post format => {"id": id, "method": method, "params": [params]}
        params = data.params or list()  # sgminer don't have
        log.debug("RpcRequest: method={} params={}".format(data.method, params))
        if not isinstance(params, list):
            return res_failed("Params is list. not {}".format(type(params)), data.id)

        # find method function and throw task
        fnc = globals().get(data.method)
        if fnc is None:
            return res_failed("not found method {}".format(data.method), data.id)
        result = await fnc(*params, user=user, password=password)
        log.debug("RpcResponse: {}".format(result))
        return res_success(result, data.id)
    except Exception as e:
        tb = traceback.format_exc()
        log.debug("JsonRpcError:", exc_info=True)
        return res_failed(str(e), data.id)


def res_failed(error, uuid):
    return {
        'id': uuid,
        'result': None,
        'error': error,
    }


def res_success(result, uuid):
    return {
        'id': uuid,
        'result': result,
        'error': None,
    }


__all__ = [
    "json_rpc",
]
