# insight API-ref
# https://blockexplorer.com/api-ref

from aiohttp import web
import aiohttp_cors
from .mainstatus import *
from .accountinfo import *
from .editaccount import *
from .chaininfo import *
from .websocket import *
from .createtx import *
from .contracttx import *
from bc4py.config import V
from bc4py.user.api import web_base
import threading
import logging
import os


def escape_cross_origin_block(app):
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            # Access-Control-Allow-Origin
            allow_credentials=True,
            expose_headers="*",
            allow_headers=("X-Requested-With", "Content-Type"),
            allow_methods=['POST', 'GET']
        )
    })
    for resource in app.router.resources():
        cors.add(resource)


def create_rest_server(f_local, port):
    threading.current_thread().setName("REST")
    app = web.Application()
    routes = web.RouteTableDef()
    V.API_OBJ = app

    @routes.post("/api/test")
    async def test_page0(request):
        post = await web_base.content_type_json_check(request)
        return web.json_response(data=post)

    @routes.get("/api/test")
    async def test_page1(request):
        get = dict(request.query)
        return web.json_response(data=get)

    @routes.get("/")
    async def help_page(request):
        header = "<H>Help page</H><BR>"
        rest = [
            ('test', 'GET or POST', '*args', 'echo GET or POST parameters.'),
            ('getsysteminfo', 'GET', '', 'System info'),
            ('getchaininfo', 'GET', '', 'Chain info'),
            ('validatorinfo', 'GET', '', 'Validator info.'),
            ('listbalance', 'GET', '[confirm=6]', 'All account balance.'),
            ('listtransactions', 'GET', '[page=0 limit=25]', 'Get account transactions.'),
            ('listunspents', 'GET', '', 'Get all unspent and orphan txhash:txindex pairs.'),
            ('listaccountaddress', 'GET', '[account=Unknown]', 'Get account related addresses.'),

            ('lock', 'GET', '', 'Lock by random bytes key.'),
            ('unlock', 'POST', '[password=None]', 'Unlock database by key.'),
            ('changepassword', 'POST', '[old=None] [new=None]', 'Change password.'),

            ('move', 'POST', '[from=Unknown] [to] [coin_id=0] [amount]', 'Move account balance of single coin.'),
            ('movemany', 'POST', '[from=Unknown] [to] [coins]', 'Move account balance of many coins.'),
            ('sendfrom', 'POST', '[from=Unknown] [address] [coin_id=0] [amount] [message=None]', 'Send from account to address.'),
            ('sendmany', 'POST', '[from=Unknown] [pairs:list(address,coin_id,amount)] [message=None]', 'Send to many account'),
            ('issueminttx', 'POST', '[name] [unit] [amount] [digit=0] <BR>\n'
                                    '[message=None] [image=None] [additional_issue=True] [account=Unknown]', 'Issue mintcoin.'),
            ('changeminttx', 'POST', '[mint_id] [amount=0] [message=None] [image=None]<BR>\n'
                                     '[additional_issue=None] [group=Unknown]', 'Chainge mintcoin.'),
            ('newaddress', 'GET', '[account=Unknown]', 'Get new bind account address.'),
            ('getkeypair', 'GET', '[address]', 'Get priKey:pubKey by address.'),

            ('createrawtx', 'POST', '[version=1] [type=TRANSFER] [time=now] [deadline=now+10800] <BR>\n'
                                    '[inputs:list((txhash, txindex),..)] <BR>\n'
                                    '[outputs:list((address, coin_id, amount),..)] <BR>\n'
                                    '[gas_price=MINIMUM_PRICE] [gas_amount=MINIMUM_AMOUNT] <BR>\n'
                                    '[message_type=None] [message=None]', 'Create raw tx without signing.'),
            ('signrawtx', 'POST', '[hex] [pk=list(sk,..)]', 'Sign raw tx by manually'),
            ('broadcasttx', 'POST', '[hex] [signature:list([pk, sign],..)]', 'Send raw tx by manually.'),

            ('contracthistory', 'GET', '[address]', 'Get contract related txhash(start:finish) pairs.'),
            ('contractdetail', 'GET', '[address]', 'Get contract detail by address.'),
            ('contractstorage', 'GET', '[address]', 'Get contract storage.'),
            ('sourcecompile', 'POST', '[source OR path] [name=None]', 'Python code to hexstr.'),
            ('contractcreate', 'POST', '[hex] [account=Unknown]', 'register contract to blockchain.'),
            ('contractstart', 'POST', '[address] [method] [args=None] [gas_limit=100000000] [outputs=list()] <BR>\n'
                                      '[account=Unknown]', 'create and send start contract.'),

            ('getblockbyheight', 'GET', '[height]', 'Get blockinfo by height.'),
            ('getblockbyhash', 'GET', '[blockhash]', 'Get blockinfo by blockhash.'),
            ('gettxbyhash', 'GET', '[txhash]', 'Get tx by txhash.'),
            ('getmintinfo', 'GET', '[mint_id]', 'Get mintcoin info.'),
        ]
        L = ["<TR><TH>URI</TH> <TH>Method</TH> <TH>Params</TH> <TH>Message</TH></TR>"]
        for cmd, method, params, msg in rest:
            s = "<TD><A href=\"./api/{}\">http://127.0.0.1:{}/api/{}</A></TD>".format(cmd, port, cmd)
            s += "<TD>{}</TD>".format(method)
            s += "<TD>{}</TD>".format(params)
            s += "<TD>{}</TD>".format(msg)
            L.append("<TR>" + s + "</TR>")
        message = "<TABLE class=\"table4\" border=1>" + "\n".join(L) + "</TABLE>"
        websocket = "Websocket API." \
                    "<TABLE class=\"table4\" border=1>" \
                    "<TR><TH></TH> <TH></TH> <TH></TH></TR>" \
                    "<TR><TD></TD> <TD></TD> <TD></TD></TR>" \
                    "</TABLE>"
        comment = "If raised error, return string error message. If success, return object except string.<BR>" \
                  "Please detect error by string or other objects."
        css = "<style>.table4 {  border-collapse: collapse;  width: 100%;}" \
              ".table4 th, .table4 td {  border: 1px solid gray;}</style>"
        return web.Response(text=header+message+css+comment, headers=web_base.CONTENT_TYPE_HTML)

    @routes.get("/api/stop")
    async def stop_system(request):
        return web.Response(text='Not found method.', status=400)

    # Base
    app.router.add_get('/api/getsysteminfo', system_info)
    app.router.add_get('/api/getchaininfo', chain_info)
    app.router.add_get('/api/validatorinfo', validator_info)
    # Account
    app.router.add_get('/api/listbalance', list_balance)
    app.router.add_get('/api/listtransactions', list_transactions)
    app.router.add_get('/api/listunspents', list_unspents)
    app.router.add_get('/api/listaccountaddress', list_account_address)
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
    # BLockChain
    app.router.add_get('/api/getblockbyheight', get_block_by_height)
    app.router.add_get('/api/getblockbyhash', get_block_by_hash)
    app.router.add_get('/api/gettxbyhash', get_tx_by_hash)
    app.router.add_get('/api/getmintinfo', get_mintcoin_info)
    # Websocket
    init_ws_status(app)
    app.router.add_get('/streaming', ws_streaming)
    # WebPage
    base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

    @routes.get('/{page_path:[^{}]+.}')
    async def web_page(request):
        page_path = request.match_info.get('page_path', "index.html")
        try:
            req_path = page_path.split("/")
            abs_path = os.path.join(base_path, os.path.join(*req_path))
            print("access to", page_path)
            if not os.path.exists(abs_path):
                return "Not found Request page.", 404
            elif os.path.isfile(abs_path):
                return web.Response(
                    body=open(abs_path, mode='rb').read(),
                    headers=web_base.CONTENT_TYPE_HTML)
            else:
                return web.Response(
                    body=open(os.path.join(abs_path, 'index.html'), mode='rb').read(),
                    headers=web_base.CONTENT_TYPE_HTML)
        except Exception as e:
            return web.Response(text=str(e), status=400)

    @routes.post('/{page_path:[^{}]+.}')
    async def dummy_page(request):
        page_path = request.match_info.get('page_path', "index.html")
        return web.Response(text='You access to "{}"'.format(page_path), status=404)

    # OperatorのPATHを追加
    app.router.add_routes(routes)

    # オリジン間リソース共有
    escape_cross_origin_block(app)

    # Working
    host = '127.0.0.1' if f_local else '0.0.0.0'
    logging.info("REST work on port={} mode={}.".format(port, 'Local' if f_local else 'Global'))
    web.run_app(app=app, host=host, port=port)
