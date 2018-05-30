from bc4py.config import C, V, P, BlockChainError
from bc4py.user import CoinObject
from bc4py.user.txcreation import *
from bc4py.database.chain.read import read_tx_output
from bc4py.database.create import closing, create_db
from bc4py.user.network.sendnew import send_newtx
from bc4py.chain.tx import TX
from bc4py.user.utils import message2signature
from bc4py.user.api import web_base
from aiohttp import web
from binascii import hexlify, unhexlify
from nem_ed25519.base import Encryption
import time


async def send_from(request):
    if P.F_NOW_BOOTING:
        return web.Response(text='Now booting...', status=403)
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            try:
                from_group = post.get('from', C.ANT_UNKNOWN)
                to_address = post['address']
                coin_id = int(post.get('coin_id', 0))
                amount = int(post['amount'])
                coins = CoinObject(coin_id, amount)
                message = post.get('message', None)
                if message:
                    msg_type = C.MSG_PLAIN
                    msg_body = message.encode()
                else:
                    msg_type = C.MSG_NONE
                    msg_body = b''
                new_tx = sendfrom(from_group, to_address, coins, chain_cur, account_cur,
                                  fee_coin_id=0, msg_type=msg_type, msg_body=msg_body, retention=10800)
                if not send_newtx(new_tx=new_tx, chain_cur=chain_cur, account_cur=account_cur):
                    raise BaseException('Failed to send new tx.')
                chain_db.commit()
                account_db.commit()
                return web_base.json_res({'txhash': hexlify(new_tx.hash).decode()})
            except Exception as e:
                chain_db.rollback()
                account_db.rollback()
                return web_base.error_res()


async def send_many(request):
    if P.F_NOW_BOOTING:
        return web.Response(text='Now booting...', status=403)
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            try:
                from_group = post.get('from', C.ANT_UNKNOWN)
                address_coin_list = list()
                for address, coin_id, amount in post['pairs']:
                    address_coin_list.append((address, int(coin_id), int(amount)))
                message = post.get('message', None)
                if message:
                    msg_type = C.MSG_PLAIN
                    msg_body = message.encode()
                else:
                    msg_type = C.MSG_NONE
                    msg_body = b''
                new_tx = sendmany(from_group, address_coin_list, chain_cur, account_cur,
                                  fee_coin_id=0, msg_type=msg_type, msg_body=msg_body, retention=10800)
                if not send_newtx(new_tx=new_tx, chain_cur=chain_cur, account_cur=account_cur):
                    raise BaseException('Failed to send new tx.')
                chain_db.commit()
                account_db.commit()
                return web_base.json_res({'txhash': hexlify(new_tx.hash).decode()})
            except Exception as e:
                chain_db.rollback()
                account_db.rollback()
                return web_base.error_res()


async def create_raw_tx(request):
    # [version=1] [type=TRANSFER] [time=now] [deadline=now+10800]
    # [inputs:list()] [outputs:list()]
    # [gas_price=MINIMUM_PRICE] [gas_amount=MINIMUM_AMOUNT]
    # [message_type=None] [message=None]
    post = await web_base.content_type_json_check(request)
    try:
        publish_time = post.get('time', int(time.time()) - V.BLOCK_GENESIS_TIME)
        deadline_time = post.get('deadline', publish_time + 10800)
        message_type = int(post.get('message_type', C.MSG_NONE))
        if message_type == C.MSG_NONE:
            message = b''
        elif message_type == C.MSG_BYTE:
            message = unhexlify(post['message'].encode())
        elif message_type == C.MSG_PLAIN:
            message = post['message'].encode()
        else:
            message = b''
        inputs = list()
        input_address = set()
        with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
            cur = db.cursor()
            for txhash, txindex in post.get('inputs', list()):
                txhash = unhexlify(txhash.encode())
                inputs.append((txhash, txindex))
                address, coin_id, amount = read_tx_output(txhash=txhash, txindex=txindex, cur=cur)
                input_address.add(address)
        tx = TX(tx={
            'version': post.get('version', 1),
            'type': post.get('type', C.TX_TRANSFER),
            'time': publish_time,
            'deadline': deadline_time,
            'inputs': inputs,
            'outputs': post.get('outputs', list()),
            'gas_price': post.get('gas_price', V.COIN_MINIMUM_PRICE),
            'gas_amount': 0,
            'message_type': message_type,
            'message': message})
        tx_size = tx.getsize() + len(input_address)*96
        tx.gas_amount = post.get('gas_amount', tx_size)
        tx.serialize()
        return web_base.json_res({
            'tx': tx.getinfo(),
            'binary': hexlify(tx.b).decode()})
    except BaseException:
        return web_base.error_res()


async def sign_raw_tx(request):
    post = await web_base.content_type_json_check(request)
    try:
        binary = unhexlify(post['binary'].encode())
        ecc = Encryption()
        other_pairs = dict()
        for sk in post.get('pairs', list()):
            ecc.sk = unhexlify(sk.encode())
            ecc.public_key()
            ecc.get_address()
            sign = (ecc.pk, ecc.sign(msg=binary, encode='raw'))
            other_pairs[ecc.ck] = sign
        tx = TX(binary=binary)
        with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
            cur = db.cursor()
            for txhash, txindex in tx.inputs:
                address, coin_id, amount = read_tx_output(txhash=txhash, txindex=txindex, cur=cur)
                try:
                    sign = message2signature(raw=tx.b, address=address)
                    tx.signature.append(sign)
                except BlockChainError:
                    if address not in other_pairs:
                        raise BlockChainError('Not found secret key "{}"'.format(address))
                    tx.signature.append(other_pairs[address])
        data = tx.getinfo()
        return web_base.json_res({
            'txhash': data['hash'],
            'signature': data['signature']})
    except BaseException:
        import traceback
        return web_base.error_res()


async def broadcast_tx(request):
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            try:
                binary = unhexlify(post['binary'].encode())
                new_tx = TX(binary=binary)
                new_tx.signature = [(pk, unhexlify(sign.encode())) for pk, sign in post['signature']]
                if not send_newtx(new_tx=new_tx, chain_cur=chain_cur, account_cur=account_cur):
                    raise BaseException('Failed to send new tx.')
                chain_db.commit()
                account_db.commit()
                return web_base.json_res({'txhash': hexlify(new_tx.hash).decode()})
            except BaseException:
                chain_db.rollback()
                account_db.rollback()
                return web_base.error_res()


async def issue_mint_tx(request):
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            try:
                mint, mintcoin_tx = issue_mintcoin(
                    name=post['name'],
                    unit=post['unit'],
                    amount=int(post['amount']),
                    digit=int(post.get('digit', 0)),
                    chain_cur=chain_cur, account_cur=account_cur,
                    message=post.get('message', None),
                    image=post.get('image', None),
                    additional_issue=bool(post.get('additional_issue', True)),
                    from_group=post.get('group', C.ANT_UNKNOWN))
                if not send_newtx(mintcoin_tx, chain_cur, account_cur):
                    raise BaseException('Failed to send new tx.')
                # print(mint.getinfo())
                # print(mintcoin_tx.getinfo(), hexlify(mintcoin_tx.b).decode())
                chain_db.commit()
                account_db.commit()
                data = mintcoin_tx.getinfo()
                return web_base.json_res({
                    'txhash': data['hash'],
                    'mintcoin': mint.getinfo()})
            except BaseException:
                return web_base.error_res()


async def change_mint_tx(request):
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            try:
                mint, mintcoin_tx = change_mintcoin(
                    mint_id=int(post['mint_id']),
                    chain_cur=chain_cur, account_cur=account_cur,
                    amount=int(post.get('amount', 0)),
                    message=post.get('message', None),
                    image=post.get('image', None),
                    additional_issue= bool(post['additional_issue']) if 'additional_issue' in post else None,
                    from_group=post.get('group', C.ANT_UNKNOWN))
                if not send_newtx(mintcoin_tx, chain_cur, account_cur):
                    raise BaseException('Failed to send new tx.')
                chain_db.commit()
                account_db.commit()
                data = mintcoin_tx.getinfo()
                return web_base.json_res({
                    'txhash': data['hash'],
                    'mintcoin': mint.getinfo()})
            except BaseException:
                return web_base.error_res()

__all__ = [
    "send_from",
    "send_many",
    "create_raw_tx",
    "sign_raw_tx",
    "broadcast_tx",
    "issue_mint_tx",
    "change_mint_tx"
]
