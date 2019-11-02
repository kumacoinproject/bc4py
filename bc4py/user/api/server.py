from bc4py.user.api.ep_system import *
from bc4py.user.api.ep_account import *
from bc4py.user.api.ep_sending import *
from bc4py.user.api.ep_blockchain import *
from bc4py.user.api.ep_wallet import *
from bc4py.user.api.ep_others import *
from bc4py.user.api.ep_websocket import *
from bc4py.user.api.jsonrpc import json_rpc
from bc4py.user.api.utils import *
from bc4py.config import V
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
import uvicorn
import asyncio
from logging import getLogger

# insight API-ref
# https://blockexplorer.com/api-ref

log = getLogger('bc4py')
loop = asyncio.get_event_loop()


async def setup_rest_server(port=3000, host='127.0.0.1', extra_locals=None, **kwargs):
    """
    create REST server for API
    :param extra_locals: add local address ex."1.2.3.4+5.6.7.8+4.5.6.7"
    :param port: REST bind port
    :param host: REST bind host, "0.0.0.0" is not restriction
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
    app.add_api_route('/private/move', move_one, methods=['POST'], **api_kwargs)
    app.add_api_route('/private/movemany', move_many, methods=['POST'], **api_kwargs)
    # Wallet
    api_kwargs = dict(tags=['Wallet'], response_class=IndentResponse)
    app.add_api_route('/private/newaddress', new_address, **api_kwargs)
    app.add_api_route('/private/getkeypair', get_keypair, **api_kwargs)
    app.add_api_route('/private/createwallet', create_wallet, methods=['POST'], **api_kwargs)
    app.add_api_route('/private/importprivatekey', import_private_key, methods=['POST'], **api_kwargs)
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
    app.add_api_websocket_route('/private/ws', private_websocket_route)
    app.add_api_route('/private/ws', private_websocket_route, **api_kwargs)
    app.add_api_route('/', json_rpc, methods=['POST'], **api_kwargs)

    # Cross-Origin Resource Sharing
    app.add_middleware(
        CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=["*"])

    # Gzip compression response
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # reject when node is booting and redirect /
    app.add_middleware(ConditionCheckMiddleware)

    # add extra local address
    if extra_locals:
        local_address.update(extra_locals.split('+'))

    # setup config
    config = uvicorn.Config(app, host=host, port=port, **kwargs)
    config.setup_event_loop()
    config.load()

    # setup server
    server = uvicorn.Server(config)
    server.logger = config.logger_instance
    server.lifespan = config.lifespan_class(config)
    # server.install_signal_handlers()  # ignore Ctrl+C
    await server.startup()
    asyncio.run_coroutine_threadsafe(server.main_loop(), loop)
    log.info(f"API listen on {host}:{port}")
    V.API_OBJ = server


async def system_resync():
    """
    This end-point make system resync. It will take many time.
    """
    from bc4py.config import P
    log.warning("Manual set booting flag to go into resync mode")
    P.F_NOW_BOOTING = True
    return 'set booting mode now'


async def system_close():
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
