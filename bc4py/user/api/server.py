from .baseinfo import *
from .accountinfo import *
from .editaccount import *
from .usertool import *
from .chaininfo import *
from .websocket import *
from .createtx import *
from .jsonrpc import json_rpc
from bc4py.config import V
from bc4py.user.api.utils import *
from fastapi import FastAPI, Depends
from fastapi.security import HTTPBasicCredentials
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
import uvicorn
import asyncio
from logging import getLogger

# insight API-ref
# https://blockexplorer.com/api-ref

log = getLogger('bc4py')
loop = asyncio.get_event_loop()


async def setup_rest_server(
        user='user', pwd='password', port=3000, host='127.0.0.1', **kwargs):
    """
    create REST server for API
    :param user: BasicAuth username
    :param pwd: BasicAuth password
    :param port: REST bind port
    :param host: REST bind host, "0.0.0.0" is global
    """
    app = FastAPI(
        version=__api_version__,
        title="bc4py API documents",
        description="OpenAPI/Swagger-generated API Reference Documentation, "
                    "[Swagger-UI](./docs) and [React based](./redoc)",
    )

    # System
    api_kwargs = dict(tags=['System'], response_class=IndentResponse)
    app.add_api_route('/public/getsysteminfo', system_info, **api_kwargs)
    app.add_api_route('/private/getsysteminfo', system_private_info, **api_kwargs)
    app.add_api_route('/public/getchaininfo', chain_info, **api_kwargs)
    app.add_api_route('/private/chainforkinfo', chain_fork_info, **api_kwargs)
    app.add_api_route('/public/getnetworkinfo', network_info, **api_kwargs)
    app.add_api_route('/private/resync', system_resync, **api_kwargs)
    app.add_api_route('/private/stop', system_close, **api_kwargs)
    # Account
    api_kwargs = dict(tags=['Account'], response_class=IndentResponse)
    app.add_api_route('/private/listbalance', list_balance, **api_kwargs)
    app.add_api_route('/private/listtransactions', list_transactions, **api_kwargs)
    app.add_api_route('/public/listunspents', list_unspents, **api_kwargs)
    app.add_api_route('/private/listunspents', list_private_unspents, **api_kwargs)
    app.add_api_route('/private/listaccountaddress', list_account_address, **api_kwargs)
    app.add_api_route('/private/createwallet', create_wallet, methods=['POST'], **api_kwargs)
    app.add_api_route('/private/importprivatekey', import_private_key, methods=['POST'], **api_kwargs)
    app.add_api_route('/private/move', move_one, methods=['POST'], **api_kwargs)
    app.add_api_route('/private/movemany', move_many, methods=['POST'], **api_kwargs)
    app.add_api_route('/private/newaddress', new_address, **api_kwargs)
    app.add_api_route('/private/getkeypair', get_keypair, **api_kwargs)
    # Sending
    api_kwargs = dict(tags=['Sending'], response_class=IndentResponse)
    app.add_api_route('/public/createrawtx', create_raw_tx, methods=['POST'], **api_kwargs)
    app.add_api_route('/public/broadcasttx', broadcast_tx, methods=['POST'], **api_kwargs)
    app.add_api_route('/private/sendfrom', send_from_user, methods=['POST'], **api_kwargs)
    app.add_api_route('/private/sendmany', send_many_user, methods=['POST'], **api_kwargs)
    app.add_api_route('/private/issueminttx', issue_mint_tx, methods=['POST'], **api_kwargs)
    app.add_api_route('/private/changeminttx', change_mint_tx, methods=['POST'], **api_kwargs)
    # Blockchain
    api_kwargs = dict(tags=['Blockchain'], response_class=IndentResponse)
    app.add_api_route('/public/getblockbyheight', get_block_by_height, **api_kwargs)
    app.add_api_route('/public/getblockbyhash', get_block_by_hash, **api_kwargs)
    app.add_api_route('/public/gettxbyhash', get_tx_by_hash, **api_kwargs)
    app.add_api_route('/public/getmintinfo', get_mintcoin_info, **api_kwargs)
    app.add_api_route('/public/getminthistory', get_mintcoin_history, **api_kwargs)
    # Others
    api_kwargs = dict(tags=['Others'], response_class=IndentResponse)
    app.add_api_route('/private/createbootstrap', create_bootstrap, **api_kwargs)
    app.add_api_websocket_route('/public/ws', websocket_route)
    app.add_api_route('/public/ws', websocket_route, **api_kwargs)
    app.add_api_websocket_route('/private/ws', websocket_route)
    app.add_api_route('/private/ws', websocket_route, **api_kwargs)
    app.add_api_route('/', json_rpc, methods=['POST'], **api_kwargs)

    # Cross-Origin Resource Sharing
    app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'])

    # Gzip compression response
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # reject when node is booting and redirect /
    app.add_middleware(ConditionCheckMiddleware)

    # setup basic auth
    assert isinstance(user, str) and isinstance(pwd, str)
    setup_basic_auth_params(user, pwd, **kwargs)

    # Working
    config = uvicorn.Config(app, host=host, port=port, **kwargs)
    config.setup_event_loop()
    server = uvicorn.Server(config)
    asyncio.run_coroutine_threadsafe(server.serve(), loop)
    log.info(f"API listen on {host}:{port}")
    V.API_OBJ = server


async def system_resync(credentials: HTTPBasicCredentials = Depends(auth)):
    """
    This end-point make system resync. It will take many time.
    """
    from bc4py.config import P
    log.warning("Manual set booting flag to go into resync mode")
    P.F_NOW_BOOTING = True
    return 'set booting mode now'


async def system_close(credentials: HTTPBasicCredentials = Depends(auth)):
    """
    This end-point make system close.
    It take a few seconds.
    """
    log.info("closing now")
    from bc4py.exit import system_safe_exit
    asyncio.run_coroutine_threadsafe(system_safe_exit(), loop)
    return 'closing now'


__all__ = [
    "setup_rest_server",
]
