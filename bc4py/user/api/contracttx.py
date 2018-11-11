from bc4py.config import C, V
from bc4py.contract.tools import *
from bc4py.user.txcreation.contract import *
from bc4py.database.create import closing, create_db
from bc4py.database.tools import *
from bc4py.database.account import *
from bc4py.database.builder import tx_builder
from bc4py.user.network.sendnew import send_newtx
from bc4py.user.api import web_base
from binascii import hexlify, unhexlify
from time import time


async def contract_init(request):
    start = time()
    post = await web_base.content_type_json_check(request)
    c_address = post['c_address']
    c_bin = unhexlify(post['c_bin'].encode())
    c_extra_imports = post.get('extra_imports', None)
    c_settings = post.get('settings', None)
    try:
        binary2contract(c_bin)  # can compile?
        sender_name = post.get('account', C.ANT_NAME_UNKNOWN)
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            sender = read_name2user(sender_name, cur)
            tx = create_init_contract_tx(c_address=c_address, c_bin=c_bin, cur=cur,
                                         c_extra_imports=c_extra_imports, c_settings=c_settings, sender=sender)
            if not send_newtx(new_tx=tx, outer_cur=cur):
                raise BaseException('Failed to send new tx.')
            db.commit()
            return web_base.json_res({
                'hash': hexlify(tx.hash).decode(),
                'gas_amount': tx.gas_amount,
                'gas_price': tx.gas_price,
                'fee': tx.gas_amount * tx.gas_price,
                'time': round(time()-start, 3)})
    except BaseException:
        return web_base.error_res()


async def contract_update(request):
    pass


async def contract_transfer(request):
    pass


async def validator_edit(request):
    start = time()
    post = await web_base.content_type_json_check(request)
    c_address = post.get('c_address', None)
    new_address = post.get('new_address', None)
    flag = int(post.get('flag', F_NOP))
    sig_diff = int(post.get('sig_diff', 0))
    try:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            if c_address is None:
                c_address = create_new_user_keypair(name=C.ANT_NAME_CONTRACT, cur=cur)
            tx = create_validator_edit_tx(c_address=c_address, cur=cur,
                                          new_address=new_address, flag=flag, sig_diff=sig_diff)
            if not send_newtx(new_tx=tx, outer_cur=cur):
                raise BaseException('Failed to send new tx.')
            db.commit()
            return web_base.json_res({
                'hash': hexlify(tx.hash).decode(),
                'gas_amount': tx.gas_amount,
                'gas_price': tx.gas_price,
                'fee': tx.gas_amount * tx.gas_price,
                'time': round(time()- start, 3)})
    except BaseException:
        return web_base.error_res()


async def validate_unconfirmed(request):
    start = time()
    post = await web_base.content_type_json_check(request)
    try:
        txhash = unhexlify(post['hash'].encode())
        tx = tx_builder.get_tx(txhash=txhash)
        if tx is None or tx.height is not None:
            return web_base.error_res('No validation tx. {}'.format(tx))
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            new_tx = create_signed_tx_as_validator(tx=tx)
            assert tx is not new_tx, 'tx={}, new_tx={}'.format(id(tx), id(new_tx))
            if not send_newtx(new_tx=new_tx, outer_cur=cur):
                raise BaseException('Failed to send new tx.')
            db.commit()
            return web_base.json_res({
                'hash': hexlify(new_tx.hash).decode(),
                'gas_amount': new_tx.gas_amount,
                'gas_price': new_tx.gas_price,
                'fee': new_tx.gas_amount * new_tx.gas_price,
                'time': round(time() - start, 3)})
    except BaseException:
        return web_base.error_res()


"""async def contract_detail(request):
    try:
        c_address = request.query['address']
        c_bin = get_contract_binary(c_address)
        c_cs = get_contract_storage(c_address)
        c_cs_data = {k.decode(errors='ignore'): v.decode(errors='ignore')
                     for k, v in c_cs.key_value.items()}
        c_obj = binary2contract(c_bin)
        contract_dis = contract2dis(c_obj)
        data = {
            'c_address': c_address,
            'c_cs_data': c_cs_data,
            'c_cs_ver': c_cs.version,
            'contract_dis': contract_dis,
            'c_bin': hexlify(c_bin).decode()}
        return web_base.json_res(data)
    except BaseException:
        return web_base.error_res()"""


"""async def contract_history(request):
    try:
        c_address = request.query['address']
        data = list()
        for index, start_hash, finish_hash, height, on_memory in get_contract_history_iter(c_address):
            data.append({
                'index': index,
                'height': height,
                'on_memory': on_memory,
                'start_hash': hexlify(start_hash).decode(),
                'finish_hash': hexlify(finish_hash).decode()})
        return web_base.json_res(data)
    except BaseException:
        return web_base.error_res()"""


"""async def contract_storage(request):
    try:
        c_address = request.query['address']
        cs = get_contract_storage(c_address)
        data = {
            'storage': {k.decode(errors='ignore'): v.decode(errors='ignore') for k, v in cs.items()},
            'version': cs.version}
        return web_base.json_res(data)
    except BaseException:
        return web_base.error_res()"""


async def source_compile(request):
    post = await web_base.content_type_json_check(request)
    try:
        if 'source' in post:
            source = str(post['source'])
            c_obj = string2contract(source, limit_global=False)
        elif 'path' in post:
            c_obj = path2contract(path=post['path'], limit_global=False)
        else:
            raise BaseException('You need set "source" or "path".')
        c_bin = contract2binary(c_obj)
        c_dis = contract2dis(c_obj)
        return web_base.json_res({
            'hex': hexlify(c_bin).decode(),
            'dis': c_dis})
    except BaseException:
        return web_base.error_res()


"""async def contract_create(request):
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_ACCOUNT_PATH, f_on_memory=True)) as db:
        cur = db.cursor()
        try:
            # バイナリをピックルしオブジェクトに戻す
            c_bin = unhexlify(post['hex'].encode())
            c_cs = {k.encode(errors='ignore'): v.encode(errors='ignore')
                    for k, v in post.get('c_cs', dict()).items()}
            binary2contract(c_bin)  # can compile?
            sender_name = post.get('account', C.ANT_NAME_UNKNOWN)
            sender_id = read_name2user(sender_name, cur)
            c_address, c_tx = create_contract_tx(c_bin, cur, sender_id, c_cs)
            if not send_newtx(new_tx=c_tx, outer_cur=cur):
                raise BaseException('Failed to send new tx.')
            db.commit()
            data = {
                'txhash': hexlify(c_tx.hash).decode(),
                'c_address': c_address,
                'time': c_tx.time,
                'fee': {
                    'gas_price': c_tx.gas_price,
                    'gas_amount': c_tx.gas_amount,
                    'total': c_tx.gas_price * c_tx.gas_amount}}
            return web_base.json_res(data)
        except BaseException:
            return web_base.error_res()"""


"""async def contract_start(request):
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_ACCOUNT_PATH, f_on_memory=True)) as db:
        cur = db.cursor()
        try:
            c_address = post['address']
            c_method = post['method']
            c_args = post.get('args', None)
            outputs = post.get('outputs', list())
            account = post.get('account', C.ANT_NAME_UNKNOWN)
            user_id = read_name2user(account, cur)
            # TX作成
            outputs = [(address, coin_id, amount) for address, coin_id, amount in outputs]
            start_tx = start_contract_tx(c_address, c_method, cur, c_args, outputs, user_id)
            # 送信
            if not send_newtx(new_tx=start_tx, outer_cur=cur):
                raise BaseException('Failed to send new tx.')
            db.commit()
            data = {
                'txhash': hexlify(start_tx.hash).decode(),
                'time': start_tx.time,
                'c_address': c_address,
                'fee': {
                    'gas_price': start_tx.gas_price,
                    'gas_amount': start_tx.gas_amount,
                    'total': start_tx.gas_price * start_tx.gas_amount},
                'params': {
                    'method': c_method,
                    'args': c_args}
            }
            return web_base.json_res(data)
        except BaseException:
            return web_base.error_res()"""


__all__ = [
    # "contract_detail",
    # "contract_history",
    # "contract_storage",
    "contract_init",
    "contract_update",
    "contract_transfer",
    "validator_edit",
    "validate_unconfirmed",
    "source_compile",
    # "contract_create",
    # "contract_start",
]
