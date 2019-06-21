# insight API-ref
# https://blockexplorer.com/api-ref

from aiohttp import web
from aiohttp_basicauth_middleware import basic_auth_middleware
from aiohttp_basicauth_middleware.strategy import BaseStrategy
import aiohttp_cors
from .baseinfo import *
from .accountinfo import *
from .editaccount import *
from .usertool import *
from .chaininfo import *
from .websocket import *
from .createtx import *
from .jsonrpc import json_rpc
from bc4py.config import V
from bc4py.user.api import utils
import threading
import os
import asyncio
from ssl import SSLContext, PROTOCOL_SSLv23
from logging import getLogger, INFO

log = getLogger('bc4py')
loop = asyncio.get_event_loop()
base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
markdown_template = open(os.path.join(base_path, 'md_renderer.html'), mode='r', encoding='utf8').read()
getLogger('aiohttp_basicauth_middleware').setLevel(INFO)

localhost_urls = {
    "localhost",
    "127.0.0.1",
}


def escape_cross_origin_block(app):
    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*":
                aiohttp_cors.ResourceOptions(
                    # Access-Control-Allow-Origin
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers=("X-Requested-With", "Content-Type", "Authorization", "Content-Length"),
                    allow_methods=['POST', 'GET'])
        })
    for resource in app.router.resources():
        cors.add(resource)


class PrivateAccessStrategy(BaseStrategy):
    """
    enable access from browser with OPTIONS method
    private method access allow only from local
    proxy is on local and add X-Forwarded-Host header (option)
    """
    async def check(self):
        if self.request.method == 'OPTIONS':
            return await self.handler(self.request)
        if self.request.remote in localhost_urls:
            proxy_host = self.request.headers.get('X-Forwarded-Host')
            if proxy_host is None or proxy_host in localhost_urls:
                return await super().check()
            else:
                raise web.HTTPForbidden()
        else:
            raise web.HTTPForbidden()


def setup_ssl_context(cert, private, hostname=False):
    ssl_context = SSLContext(PROTOCOL_SSLv23)
    ssl_context.load_cert_chain(cert, private)
    ssl_context.check_hostname = hostname
    return ssl_context


def create_rest_server(user='user', pwd='password', port=3000, host='127.0.0.1', ssl_context=None):
    """
    create REST server for API
    :param user: BasicAuth username
    :param pwd: BasicAuth password
    :param port: REST bind port
    :param host: REST bind host, "0.0.0.0" is global
    :param ssl_context: for SSL server
    """
    threading.current_thread().setName("REST")
    app = web.Application()
    V.API_OBJ = app

    # System
    app.router.add_get('/public/getsysteminfo', system_info)
    app.router.add_get('/private/getsysteminfo', system_private_info)
    app.router.add_get('/public/getchaininfo', chain_info)
    app.router.add_get('/private/chainforkinfo', chain_fork_info)
    app.router.add_get('/public/getnetworkinfo', network_info)
    app.router.add_get('/private/createbootstrap', create_bootstrap)
    app.router.add_get('/private/resync', resync)
    app.router.add_get('/private/stop', close_server)
    # Account
    app.router.add_get('/private/listbalance', list_balance)
    app.router.add_get('/private/listtransactions', list_transactions)
    app.router.add_get('/public/listunspents', list_unspents)
    app.router.add_get('/private/listunspents', list_private_unspents)
    app.router.add_get('/private/listaccountaddress', list_account_address)
    app.router.add_post('/private/createwallet', create_wallet)
    app.router.add_post('/private/importprivatekey', import_private_key)
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
    # BlockChain
    app.router.add_get('/public/getblockbyheight', get_block_by_height)
    app.router.add_get('/public/getblockbyhash', get_block_by_hash)
    app.router.add_get('/public/gettxbyhash', get_tx_by_hash)
    app.router.add_get('/public/getmintinfo', get_mintcoin_info)
    app.router.add_get('/public/getminthistory', get_mintcoin_history)
    # Others
    app.router.add_get('/public/ws', websocket_route)
    app.router.add_get('/private/ws', websocket_route)
    # JSON-RPC html/markdown pages
    app.router.add_get('/', web_page)
    app.router.add_post('/', json_rpc)
    app.router.add_get('/{page_path:[^{}]+.}', web_page)

    # Cross-Origin Resource Sharing
    escape_cross_origin_block(app)

    # setup basic auth
    assert isinstance(user, str) and isinstance(pwd, str)
    app.middlewares.append(basic_auth_middleware(('/private/',), {user: pwd}, PrivateAccessStrategy))

    # Working
    runner = web.AppRunner(app)
    loop.run_until_complete(non_blocking_start(runner, host, port, ssl_context))
    log.info(f"API listen on {host}:{port}")


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
                headers=utils.CONTENT_TYPE_HTML)
        elif not os.path.exists(abs_path):
            return web.Response(text="Not found page. {}".format(req_path[-1]), status=404)
        elif os.path.isfile(abs_path):
            return web.Response(body=open(abs_path, mode='rb').read(), headers=utils.CONTENT_TYPE_HTML)
        else:
            return web.Response(
                body=open(os.path.join(abs_path, 'index.html'), mode='rb').read(),
                headers=utils.CONTENT_TYPE_HTML)
    except Exception:
        return utils.error_res()


async def resync(request):
    from bc4py.config import P
    log.warning("Manual set booting flag to go into resync mode")
    P.F_NOW_BOOTING = True
    return web.Response(text='set booting mode now')


async def close_server(request):

    def close():
        log.debug("close server now")
        loop.call_soon_threadsafe(loop.stop)

    log.info("Closing server after 5 seconds")
    import threading
    threading.Timer(interval=5.0, function=close).start()
    return web.Response(text='close server after 5 seconds')


__all__ = [
    "localhost_urls",
    "escape_cross_origin_block",
    "PrivateAccessStrategy",
    "setup_ssl_context",
    "create_rest_server",
]
