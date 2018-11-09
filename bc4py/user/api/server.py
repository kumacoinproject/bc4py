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
        if self.request.method == 'OPTIONS':
            return await self.handler(self.request)
        else:
            return await super().check()


def setup_basic_auth(app, user, pwd):
    app.middlewares.append(
        basic_auth_middleware(('/api/',), {user: pwd}, SkipOptionsStrategy))
    logging.info("Enabled basic auth.")


def setup_ssl_context(cert, private, hostname=False):
    import ssl
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ssl_context.load_cert_chain(cert, private)
    ssl_context.check_hostname = hostname
    return ssl_context


def create_rest_server(f_local, port, f_blocking=True, user=None, pwd=None, ssl_context=None):
    threading.current_thread().setName("REST")
    app = web.Application()
    routes = web.RouteTableDef()
    V.API_OBJ = app

    # Base
    app.router.add_get('/api/getsysteminfo', system_info)
    app.router.add_get('/api/getchaininfo', chain_info)
    app.router.add_get('/api/getnetworkinfo', network_info)
    # app.router.add_get('/api/validatorinfo', validator_info)
    app.router.add_get('/api/resync', resync)
    # Account
    app.router.add_get('/api/listbalance', list_balance)
    app.router.add_get('/api/listtransactions', list_transactions)
    app.router.add_get('/api/listunspents', list_unspents)
    app.router.add_get('/api/listaccountaddress', list_account_address)
    app.router.add_post('/api/lock', lock_database)
    app.router.add_post('/api/unlock', unlock_database)
    app.router.add_post('/api/changepassword', change_password)
    app.router.add_post('/api/move', move_one)
    app.router.add_post('/api/movemany', move_many)
    app.router.add_get('/api/newaddress', new_address)
    app.router.add_get('/api/getkeypair', get_keypair)
    # Sending
    app.router.add_post('/api/createrawtx', create_raw_tx)
    app.router.add_post('/api/signrawtx', sign_raw_tx)
    app.router.add_post('/api/broadcasttx', broadcast_tx)
    app.router.add_post('/api/sendfrom', send_from_user)
    app.router.add_post('/api/sendmany', send_many_user)
    app.router.add_post('/api/issueminttx', issue_mint_tx)
    app.router.add_post('/api/changeminttx', change_mint_tx)
    # Contract
    app.router.add_get('/api/contracthistory', contract_history)
    app.router.add_get('/api/contractdetail', contract_detail)
    app.router.add_get('/api/contractstorage', contract_storage)
    app.router.add_post('/api/sourcecompile', source_compile)
    app.router.add_post('/api/contractcreate', contract_create)
    app.router.add_post('/api/contractstart', contract_start)
    # BlockChain
    app.router.add_get('/api/getblockbyheight', get_block_by_height)
    app.router.add_get('/api/getblockbyhash', get_block_by_hash)
    app.router.add_get('/api/gettxbyhash', get_tx_by_hash)
    app.router.add_get('/api/getmintinfo', get_mintcoin_info)
    # Websocket
    init_ws_status(app)
    app.router.add_get('/streaming', ws_streaming)
    # Json-RPC
    app.router.add_post('/json-rpc', json_rpc)

    @routes.get('/api/stop')
    async def close_server(request):
        logging.info("Closing server...")
        import threading
        threading.Timer(5, loop.call_soon_threadsafe(loop.stop)).start()
        return web.Response(text='Close after 5 seconds.')

    @routes.get('/')
    @routes.get('/{page_path:[^{}]+.}')
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
                    text=markdown_template % (markdown_title, markdown_body),
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
            logging.error(e)
            return web.Response(text="Error: {}".format(page_path), status=400)

    @routes.post('/{page_path:[^{}]+.}')
    async def dummy_page(request):
        page_path = request.match_info.get('page_path', "index.html")
        return web.Response(text='You access to "{}"'.format(page_path), status=404)

    # OperatorのPATHを追加
    app.router.add_routes(routes)

    # オリジン間リソース共有
    escape_cross_origin_block(app)

    # setup basic auth
    if user and pwd:
        assert isinstance(user, str) and len(user) > 2
        assert isinstance(pwd, str) and len(pwd) > 7
        setup_basic_auth(app, user, pwd)
    elif f_local:
        logging.debug('non basic auth.')
    else:
        logging.error('Accept 0.0.0.0 without basic auth!')

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


async def non_blocking_start(runner, host, port, ssl_context):
    # No blocking run https://docs.aiohttp.org/en/stable/web_advanced.html#application-runners
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port, ssl_context=ssl_context)
    await site.start()


async def resync(request):
    from bc4py.config import P
    P.F_NOW_BOOTING = True
    return web.Response(text='Resync')
