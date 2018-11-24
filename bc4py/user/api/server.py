# insight API-ref
# https://blockexplorer.com/api-ref

from aiohttp import web
from aiohttp_basicauth_middleware import basic_auth_middleware
from aiohttp_basicauth_middleware.strategy import BaseStrategy
import aiohttp_cors
from .mainstatus import *
from .accountinfo import *
from .editaccount import *
from .chaininfo import *
from .websocket import *
from .createtx import *
from .contractinfo import *
from .contracttx import *
from .jsonrpc import json_rpc
from bc4py.config import V
from bc4py.user.api import web_base
import threading
import logging
import os
import asyncio


loop = asyncio.get_event_loop()
base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
markdown_template = open(os.path.join(base_path, 'md_renderer.html'), mode='r', encoding='utf8').read()


def escape_cross_origin_block(app):
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            # Access-Control-Allow-Origin
            allow_credentials=True,
            expose_headers="*",
            allow_headers=("X-Requested-With", "Content-Type", "Authorization", "Content-Length"),
            allow_methods=['POST', 'GET']
        )
    })
    for resource in app.router.resources():
        cors.add(resource)


class SkipOptionsStrategy(BaseStrategy):
    # enable access from browser with OPTIONS method
    async def check(self):
        # access allow only local
        # if self.request.remote != '127.0.0.1' or not self.request.remote.startswith('192.168.'):
        #    raise web.HTTPForbidden()
        if self.request.method == 'OPTIONS':
            return await self.handler(self.request)
        else:
            return await super().check()


def setup_basic_auth(app, user, pwd):
    app.middlewares.append(
        basic_auth_middleware(('/private/',), {user: pwd}, SkipOptionsStrategy))
    logging.info("Enabled basic auth.")


def setup_ssl_context(cert, private, hostname=False):
    import ssl
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ssl_context.load_cert_chain(cert, private)
    ssl_context.check_hostname = hostname
    return ssl_context


def create_rest_server(f_local, port, user=None, pwd=None, f_blocking=True, ssl_context=None):
    threading.current_thread().setName("REST")
    app = web.Application()
    V.API_OBJ = app

    # System
    app.router.add_get('/public/getsysteminfo', system_info)
    app.router.add_get('/private/getsysteminfo', system_private_info)
    app.router.add_get('/public/getchaininfo', chain_info)
    app.router.add_get('/public/getnetworkinfo', network_info)
    app.router.add_get('/private/resync', resync)
    app.router.add_get('/private/stop', close_server)
    # Account
    app.router.add_get('/private/listbalance', list_balance)
    app.router.add_get('/private/listtransactions', list_transactions)
    app.router.add_get('/private/listunspents', list_unspents)
    app.router.add_get('/private/listaccountaddress', list_account_address)
    # app.router.add_post('/private/lock', lock_database)  TODO: Work? Need?
    # app.router.add_post('/private/unlock', unlock_database) TODO: Work? Need?
    # app.router.add_post('/private/changepassword', change_password) TODO: Work? Need?
    app.router.add_post('/private/move', move_one)
    app.router.add_post('/private/movemany', move_many)
    app.router.add_get('/private/newaddress', new_address)
    app.router.add_get('/private/getkeypair', get_keypair)
    # Sending
    app.router.add_post('/public/createrawtx', create_raw_tx)
    app.router.add_post('/private/signrawtx', sign_raw_tx)
    app.router.add_post('/public/broadcasttx', broadcast_tx)
    app.router.add_post('/private/sendfrom', send_from_user)
    app.router.add_post('/private/sendmany', send_many_user)
    app.router.add_post('/private/issueminttx', issue_mint_tx)
    app.router.add_post('/private/changeminttx', change_mint_tx)
    # Contract
    app.router.add_get('/public/getcontractinfo', contract_info)
    app.router.add_get('/public/getvalidatorinfo', validator_info)
    app.router.add_get('/public/getcontracthistory', get_contract_history)
    app.router.add_get('/public/getvalidatorhistory', get_validator_history)
    app.router.add_get('/public/contractstorage', contract_storage)
    app.router.add_get('/private/watchinginfo', watching_info)
    app.router.add_post('/private/sourcecompile', source_compile)
    app.router.add_post('/private/contractinit', contract_init)
    app.router.add_post('/private/contractupdate', contract_update)
    app.router.add_post('/private/contracttransfer', contract_transfer)
    app.router.add_post('/private/concludecontract', conclude_contract)
    app.router.add_post('/private/validatoredit', validator_edit)
    app.router.add_post('/private/validateunconfirmed', validate_unconfirmed)
    # BlockChain
    app.router.add_get('/public/getblockbyheight', get_block_by_height)
    app.router.add_get('/public/getblockbyhash', get_block_by_hash)
    app.router.add_get('/public/gettxbyhash', get_tx_by_hash)
    app.router.add_get('/public/getmintinfo', get_mintcoin_info)
    app.router.add_get('/public/getminthistory', get_mintcoin_history)
    # Others
    start_ws_listen_loop()
    app.router.add_get('/public/ws', websocket_public)
    app.router.add_get('/private/ws', websocket_private)
    app.router.add_post('/json-rpc', json_rpc)  # Json-RPC
    # html/markdown pages
    app.router.add_get('/', web_page)
    app.router.add_get('/{page_path:[^{}]+.}', web_page)

    # route2markdown(app)

    # Cross-Origin Resource Sharing
    escape_cross_origin_block(app)

    # setup basic auth
    if user and pwd:
        assert isinstance(user, str) and len(user) > 2
        assert isinstance(pwd, str) and len(pwd) > 7
        setup_basic_auth(app, user, pwd)
    elif f_local:
        logging.debug('non basic auth.')
    else:
        raise Exception('Accept 0.0.0.0 without basic auth!')

    # Working
    host = '127.0.0.1' if f_local else '0.0.0.0'
    # web.run_app(app=app, host=host, port=port)
    runner = web.AppRunner(app)
    loop.run_until_complete(non_blocking_start(runner, host, port, ssl_context))
    logging.info("REST work on port={} mode={}.".format(port, 'Local' if f_local else 'Global'))

    if f_blocking:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        loop.close()
        logging.info("REST Server closed now.")
    else:
        logging.info("Create REST Server.")


def route2markdown(app):
    row = [('URL', 'Method', 'Type', 'About')]
    for r in app.router.routes():
        if r.method not in ('GET', 'POST'):
            continue
        if not getattr(r.resource, '_path', False):
            continue
        if len(r.resource._path.split("/")) != 3:
            continue
        *dummy, type, url = r.resource._path.split("/")
        row.append((url, r.method, type, r.handler.__doc__ or ""))
    # print(row)
    for url, method, type, about in row:
        print("|{} |{} |{} |{} |".format(
            "[/{}/{}](./{}/{})".format(type, url, type, url).ljust(60, " "),
            method.ljust(6, " "),
            type.ljust(6, " "),
            about.ljust(60, " ")
        ))


async def non_blocking_start(runner, host, port, ssl_context):
    # No blocking run https://docs.aiohttp.org/en/stable/web_advanced.html#application-runners
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port, ssl_context=ssl_context)
    await site.start()


async def web_page(request):
    page_path = request.match_info.get('page_path', "index.md")
    try:
        req_path = page_path.split("/")
        abs_path = os.path.join(base_path, *req_path)
        if page_path.endswith('.md'):
            markdown_title = req_path[-1]
            markdown_body = open(abs_path, mode='r', encoding='utf8').read()
            markdown_body = markdown_body.replace('\\', '\\\\').replace('\"', '\\\"').replace("\n", "\\n")
            return web.Response(
                text=markdown_template.replace('{:title}', markdown_title, 1).replace('{:body}', markdown_body, 1),
                headers=web_base.CONTENT_TYPE_HTML)
        elif not os.path.exists(abs_path):
            return web.Response(text="Not found page. {}".format(req_path[-1]), status=404)
        elif os.path.isfile(abs_path):
            return web.Response(
                body=open(abs_path, mode='rb').read(),
                headers=web_base.CONTENT_TYPE_HTML)
        else:
            return web.Response(
                body=open(os.path.join(abs_path, 'index.html'), mode='rb').read(),
                headers=web_base.CONTENT_TYPE_HTML)
    except Exception as e:
        logging.error(e, exc_info=True)
        return web.Response(text="Error: {}".format(page_path), status=400)


async def resync(request):
    from bc4py.config import P
    P.F_NOW_BOOTING = True
    return web.Response(text='Resync')


async def close_server(request):
    def close():
        loop.call_soon_threadsafe(loop.stop)

    logging.info("Closing server...")
    import threading
    threading.Timer(interval=5.0, function=close).start()
    return web.Response(text='Close after 5 seconds.')


__all__ = [
    "escape_cross_origin_block",
    "SkipOptionsStrategy",
    "setup_basic_auth",
    "setup_ssl_context",
    "create_rest_server",
]
