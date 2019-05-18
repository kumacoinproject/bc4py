from bc4py.config import P
from bc4py.user.api import web_base
from .account import *
from .mining import *
from .others import *
from aiohttp import web
from base64 import b64decode
from logging import getLogger
import json
import traceback

log = getLogger('bc4py')

# about "coinbasetxn"
# https://bitcoin.stackexchange.com/questions/13438/difference-between-coinbaseaux-flags-vs-coinbasetxn-data
# https://github.com/bitcoin/bips/blob/master/bip-0022.mediawiki


async def json_rpc(request):
    # JSON-RPC require BasicAuth
    if 'Authorization' not in request.headers:
        return res_failed("Not found Authorization", None)
    authorization = request.headers['Authorization']
    auth_type, auth_data = authorization.split()
    if auth_type != 'Basic':
        return res_failed("Not Basic Authorization", None)

    # user     => no meaning
    # password => mining consensus number by confing.py
    user, password = b64decode(auth_data.encode()).decode().split(':')
    post = await web_base.content_type_json_check(request)
    if not isinstance(post, dict):
        return res_failed("post data is not correct? post={}".format(post), None)
    if P.F_NOW_BOOTING:
        return res_failed("Busy status", post.get('id'))

    try:
        # post format => {"id": id, "method": method, "params": [params]}
        method = post['method']
        params = post.get('params', list())  # sgminer don't have
        log.debug("RpcRequest: method={} params={}".format(method, params))
        if not isinstance(params, list):
            return res_failed("Params is list. not {}".format(type(params)), post.get('id'))

        # find method function and throw task
        fnc = globals().get(method)
        if fnc is None:
            return res_failed("not found method {}".format(method), post.get('id'))
        result = await fnc(*params, user=user, password=password)
        log.debug("RpcResponse: {}".format(result))
        return res_success(result, post.get('id'))
    except Exception as e:
        tb = traceback.format_exc()
        log.debug("JsonRpcError:", exc_info=True)
        return res_failed(str(e), post.get('id'))


def res_failed(error, uuid):
    return web.Response(
        text=json.dumps({
            'id': uuid,
            'result': None,
            'error': error
        }), content_type='application/json')


def res_success(result, uuid):
    return web.Response(
        text=json.dumps({
            'id': uuid,
            'result': result,
            'error': None
        }), content_type='application/json')


__all__ = [
    "json_rpc",
]
