from bc4py import __chain_version__
from bc4py.config import C, V, P, BlockChainError
from bc4py.contract.utils import *
from bc4py.contract.finishtx import create_finish_tx
from bc4py.user import CoinObject
from bc4py.user.txcreation import *
from bc4py.database.chain.read import read_contract_list, read_contract_tx, read_contract_history
from bc4py.database.create import closing, create_db
from bc4py.user.network.sendnew import send_newtx
from bc4py.chain.tx import TX
from bc4py.user.utils import message2signature
from bc4py.user.api import web_base
from aiohttp import web
from binascii import hexlify, unhexlify
from nem_ed25519.base import Encryption
import bjson
import time

# 陶生病院　消化器内科　外科、豊橋病院、日赤
# 名刺大　整形外科、医療センター　脳外科
# 豊橋医療センター　泌尿器科と整形
# 愛知医科
# 名古屋東病院　内科
# 成田記念病院


"""
def contract(c_address, c_tx):\n
    # something
    return outputs, contract_storage
"""


async def contract_all_list(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        return web_base.json_res(read_contract_list(cur))


async def contract_detail(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        try:
            c_address = request.query['address']
            c_tx = read_contract_tx(c_address=c_address, cur=cur)
            c_address, c_bin = bjson.loads(c_tx.message)
            pickle_dis = binary2dis(c_bin)
            c_obj = binary2contract(c_bin)
            contract_dis = contract2dis(c_obj)
            data = c_tx.getinfo()
            data.update({
                'address': c_address,
                'pickle_dis': pickle_dis,
                'contract_dis': contract_dis
            })
            return web_base.json_res(data)
        except BaseException:
            return web_base.error_res()


async def contract_history(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        try:
            c_address = request.query['address']
            d = read_contract_history(address=c_address, cur=cur)
            return web_base.json_res([
                (hexlify(start_hash).decode(), hexlify(finish_hash).decode())
                for start_hash, finish_hash in d if start_hash and finish_hash])
        except BaseException:
            return web_base.error_res()


async def source_compile(request):
    post = await web_base.content_type_json_check(request)
    try:
        if 'source' in post:
            source = str(post['source'])
            name = str(post.get('name', None))
            c_obj = string2contract(source, name, limited=False)
        elif 'path' in post:
            c_obj = filepath2contract(path=post['path'])
        else:
            raise BaseException('You need set "source" or "path".')
        c_bin = contract2binary(c_obj)
        c_dis = contract2dis(c_obj)
        return web_base.json_res({
            'hex': hexlify(c_bin).decode(),
            'dis': c_dis})
    except BaseException:
        return web_base.error_res()


async def contract_create(request):
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_BLOCKCHAIN_PATH, f_on_memory=True)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH, f_on_memory=True)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            try:
                # バイナリをピックルしオブジェクトに戻す
                binary = unhexlify(post['hex'].encode())
                binary2contract(binary)
                from_group = post.get('group', C.ANT_UNKNOWN)
                c_address, c_tx = create_contract_tx(
                    contract=binary,
                    chain_cur=chain_cur,
                    account_cur=account_cur,
                    from_group=from_group)
                if not send_newtx(c_tx, chain_cur, account_cur):
                    raise BaseException('Failed to send new tx.')
                chain_db.commit()
                account_db.commit()
                data = c_tx.getinfo()
                return web_base.json_res({
                    'txhash': data['hash'],
                    'contract': c_address,
                    'fee': c_tx.gas_price * c_tx.gas_amount})
            except BaseException:
                return web_base.error_res()


async def contract_start(request):
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_BLOCKCHAIN_PATH, f_on_memory=True)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH, f_on_memory=True)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            try:
                c_address = post['address']
                c_data = post.get('data', None)
                outputs = post.get('outputs', list())
                from_group = post.get('group', C.ANT_UNKNOWN)
                f_broadcast = bool(post.get('send', False))
                # TX作成
                outputs = [(address, coin_id, amount) for address, coin_id, amount in outputs]
                start_tx = start_contract_tx(
                    c_address=c_address, c_data=c_data, chain_cur=chain_cur, account_cur=account_cur,
                    outputs=outputs, from_group=from_group)
                # 送信
                if f_broadcast:
                    if not send_newtx(start_tx, chain_cur, account_cur):
                        raise BaseException('Failed to send new tx.')
                    chain_db.commit()
                    account_db.commit()
                    return web_base.json_res({
                        'txhash': hexlify(start_tx.hash).decode(),
                        'address': c_address,
                        'fee': start_tx.gas_price * start_tx.gas_amount,
                        'data': c_data})
                else:
                    chain_db.rollback()
                    account_db.rollback()
                    return web_base.json_res({
                        'txhash': hexlify(start_tx.hash).decode(),
                        'address': c_address,
                        'fee': start_tx.gas_price * start_tx.gas_amount,
                        'data': c_data})
            except BaseException:
                return web_base.error_res()


__all__ = [
    "contract_all_list",
    "contract_history",
    "contract_detail",
    "source_compile",
    "contract_create",
    "contract_start",
]
