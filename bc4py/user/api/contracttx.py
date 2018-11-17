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
    try:
        c_address = post['c_address']
        c_bin = unhexlify(post['hex'].encode())
        c_extra_imports = post.get('extra_imports', None)
        c_settings = post.get('settings', None)
        send_pairs = post.get('send_pairs', None)
        binary2contract(c_bin)  # can compile?
        sender_name = post.get('from', C.ANT_NAME_UNKNOWN)
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            sender = read_name2user(sender_name, cur)
            tx = create_contract_init_tx(c_address=c_address, c_bin=c_bin, cur=cur, c_extra_imports=c_extra_imports,
                                         c_settings=c_settings, send_pairs=send_pairs, sender=sender)
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
    start = time()
    post = await web_base.content_type_json_check(request)
    try:
        c_address = post['c_address']
        if 'hex' in post:
            c_bin = unhexlify(post['hex'].encode())
            binary2contract(c_bin)  # can compile?
        else:
            c_bin = None
        c_extra_imports = post.get('extra_imports', None)
        c_settings = post.get('settings', None)
        send_pairs = post.get('send_pairs', None)
        sender_name = post.get('from', C.ANT_NAME_UNKNOWN)
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            sender = read_name2user(sender_name, cur)
            tx = create_contract_update_tx(c_address=c_address, cur=cur, c_bin=c_bin, c_extra_imports=c_extra_imports,
                                           c_settings=c_settings, send_pairs=send_pairs, sender=sender)
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


async def contract_transfer(request):
    start = time()
    post = await web_base.content_type_json_check(request)
    try:
        c_address = post['c_address']
        c_method = post['c_method']
        c_args = post['c_args']
        send_pairs = post.get('send_pairs', None)
        sender_name = post.get('from', C.ANT_NAME_UNKNOWN)
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            sender = read_name2user(sender_name, cur)
            tx = create_contract_transfer_tx(c_address=c_address, cur=cur, c_method=c_method, c_args=c_args,
                                             send_pairs=send_pairs, sender=sender)
            if not send_newtx(new_tx=tx, outer_cur=cur):
                raise BaseException('Failed to send new tx.')
            db.commit()
        return web_base.json_res({
            'hash': hexlify(tx.hash).decode(),
            'gas_amount': tx.gas_amount,
            'gas_price': tx.gas_price,
            'fee': tx.gas_amount * tx.gas_price,
            'time': round(time() - start, 3)})
    except BaseException:
        return web_base.error_res()


async def conclude_contract(request):
    start = time()
    post = await web_base.content_type_json_check(request)
    try:
        c_address = post['c_address']
        start_hash = unhexlify(post['start_hash'].encode())
        send_pairs = post.get('send_pairs', None)
        c_storage = post.get('storage', None)
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            tx = create_conclude_tx(c_address=c_address, start_hash=start_hash,
                                    cur=cur, send_pairs=send_pairs, c_storage=c_storage)
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
            return web_base.error_res('You cannot validate tx. {}'.format(tx))
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


__all__ = [
    # "contract_detail",
    # "contract_history",
    # "contract_storage",
    "contract_init",
    "contract_update",
    "contract_transfer",
    "conclude_contract",
    "validator_edit",
    "validate_unconfirmed",
    "source_compile",
    # "contract_create",
    # "contract_start",
]
