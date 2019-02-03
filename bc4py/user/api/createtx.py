from bc4py import __chain_version__
from bc4py.config import C, V, P, BlockChainError
from bc4py.user import Balance
from bc4py.user.txcreation import *
from bc4py.database.builder import tx_builder
from bc4py.database.account import *
from bc4py.database.create import closing, create_db
from bc4py.user.network.sendnew import send_newtx
from bc4py.user.api import web_base
from bc4py.chain.tx import TX
from aiohttp import web
from binascii import a2b_hex
from nem_ed25519 import public_key, get_address, sign
from time import time
import msgpack


def type2message(message_type, message):
    if message_type == C.MSG_NONE:
        return b''
    elif message_type == C.MSG_PLAIN:
        return message.encode()
    elif message_type == C.MSG_BYTE:
        return a2b_hex(message)
    elif message_type == C.MSG_MSGPACK:
        return msgpack.packb(message, use_bin_type=True)
    elif message_type == C.MSG_HASHLOCKED:
        return a2b_hex(message)
    else:
        raise Exception('Not found message type {}'.format(message_type))


async def create_raw_tx(request):
    # [version=1] [type=TRANSFER] [time=now] [deadline=now+10800]
    # [inputs:list()] [outputs:list()]
    # [gas_price=MINIMUM_PRICE] [gas_amount=MINIMUM_AMOUNT]
    # [message_type=None] [message=None]
    post = await web_base.content_type_json_check(request)
    try:
        publish_time = post.get('time', int(time() - V.BLOCK_GENESIS_TIME))
        deadline_time = post.get('deadline', publish_time + 10800)
        message_type = post.get('message_type', C.MSG_NONE)
        message = type2message(message_type, post.get('message'))
        inputs = list()
        input_address = set()
        for txhash, txindex in post.get('inputs', list()):
            txhash = a2b_hex(txhash)
            inputs.append((txhash, txindex))
            input_tx = tx_builder.get_tx(txhash)
            address, coin_id, amount = input_tx.outputs[txindex]
            input_address.add(address)
        tx = TX.from_dict(tx={
            'version': post.get('version', __chain_version__),
            'type': post.get('type', C.TX_TRANSFER),
            'time': publish_time,
            'deadline': deadline_time,
            'inputs': inputs,
            'outputs': post.get('outputs', list()),
            'gas_price': post.get('gas_price', V.COIN_MINIMUM_PRICE),
            'gas_amount': 0,
            'message_type': message_type,
            'message': message})
        require_gas = tx.size + len(input_address) * C.SIGNATURE_GAS
        tx.gas_amount = post.get('gas_amount', require_gas)
        tx.serialize()
        return web_base.json_res({
            'tx': tx.getinfo(),
            'hex': tx.b.hex()})
    except Exception:
        return web_base.error_res()


async def sign_raw_tx(request):
    post = await web_base.content_type_json_check(request)
    try:
        binary = a2b_hex(post['hex'])
        other_pairs = dict()
        for sk in post.get('pairs', list()):
            pk = public_key(sk=sk, encode=str)
            ck = get_address(pk=pk, prefix=V.BLOCK_PREFIX)
            other_pairs[ck] = (pk, sign(msg=binary, sk=sk, pk=pk))
        tx = TX.from_binary(binary=binary)
        for txhash, txindex in tx.inputs:
            input_tx = tx_builder.get_tx(txhash)
            address, coin_id, amount = input_tx.outputs[txindex]
            try:
                tx.signature.append(message2signature(raw=tx.b, address=address))
            except BlockChainError:
                if address not in other_pairs:
                    raise BlockChainError('Not found secret key "{}"'.format(address))
                tx.signature.append(other_pairs[address])
        data = tx.getinfo()
        return web_base.json_res({
            'hash': data['hash'],
            'signature': data['signature'],
            'hex': tx.b.hex()})
    except Exception:
        return web_base.error_res()


async def broadcast_tx(request):
    start = time()
    post = await web_base.content_type_json_check(request)
    try:
        binary = a2b_hex(post['hex'])
        new_tx = TX.from_binary(binary=binary)
        new_tx.signature = [(pk, a2b_hex(_sign)) for pk, _sign in post['signature']]
        if 'R' in post:
            new_tx.R = a2b_hex(post['R'])
        if not send_newtx(new_tx=new_tx):
            raise BlockChainError('Failed to send new tx.')
        return web_base.json_res({
            'hash': new_tx.hash.hex(),
            'gas_amount': new_tx.gas_amount,
            'gas_price': new_tx.gas_price,
            'fee': new_tx.gas_amount * new_tx.gas_price,
            'time': round(time() - start, 3)})
    except Exception:
        return web_base.error_res()


async def send_from_user(request):
    start = time()
    if P.F_NOW_BOOTING:
        return web.Response(text='Now booting...', status=403)
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        try:
            from_name = post.get('from', C.account2name[C.ANT_UNKNOWN])
            from_id = read_name2user(from_name, cur)
            to_address = post['address']
            coin_id = int(post.get('coin_id', 0))
            amount = int(post['amount'])
            coins = Balance(coin_id, amount)
            if 'hex' in post:
                msg_type = C.MSG_BYTE
                msg_body = a2b_hex(post['hex'])
            elif 'message' in post:
                msg_type = post.get('message_type', C.MSG_PLAIN)
                msg_body = type2message(msg_type, post['message'])
            else:
                msg_type = C.MSG_NONE
                msg_body = b''
            new_tx = send_from(from_id, to_address, coins, cur, msg_type=msg_type, msg_body=msg_body)
            if 'R' in post:
                new_tx.R = a2b_hex(post['R'])
            if not send_newtx(new_tx=new_tx, outer_cur=cur):
                raise BlockChainError('Failed to send new tx.')
            db.commit()
            return web_base.json_res({
                'hash': new_tx.hash.hex(),
                'gas_amount': new_tx.gas_amount,
                'gas_price': new_tx.gas_price,
                'fee': new_tx.gas_amount * new_tx.gas_price,
                'time': round(time() - start, 3)})
        except Exception as e:
            db.rollback()
            return web_base.error_res()


async def send_many_user(request):
    start = time()
    if P.F_NOW_BOOTING:
        return web.Response(text='Now booting...', status=403)
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        try:
            user_name = post.get('from', C.account2name[C.ANT_UNKNOWN])
            user_id = read_name2user(user_name, cur)
            send_pairs = list()
            for address, coin_id, amount in post['pairs']:
                send_pairs.append((address, int(coin_id), int(amount)))
            if 'hex' in post:
                msg_type = C.MSG_BYTE
                msg_body = a2b_hex(post['hex'])
            elif 'message' in post:
                msg_type = post.get('message_type', C.MSG_PLAIN)
                msg_body = type2message(msg_type, post['message'])
            else:
                msg_type = C.MSG_NONE
                msg_body = b''
            new_tx = send_many(user_id, send_pairs, cur, msg_type=msg_type, msg_body=msg_body)
            if not send_newtx(new_tx=new_tx, outer_cur=cur):
                raise BlockChainError('Failed to send new tx.')
            db.commit()
            return web_base.json_res({
                'hash': new_tx.hash.hex(),
                'gas_amount': new_tx.gas_amount,
                'gas_price': new_tx.gas_price,
                'fee': new_tx.gas_amount * new_tx.gas_price,
                'time': round(time() - start, 3)})
        except Exception as e:
            db.rollback()
            return web_base.error_res()


async def issue_mint_tx(request):
    start = time()
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        try:
            user_name = post.get('from', C.account2name[C.ANT_UNKNOWN])
            sender = read_name2user(user_name, cur)
            mint_id, tx = issue_mintcoin(
                name=post['name'], unit=post['unit'], digit=post.get('digit', 8),
                amount=post['amount'], cur=cur, description=post.get('description', None),
                image=post.get('image', None), additional_issue=post.get('additional_issue', True),
                sender=sender)
            if not send_newtx(new_tx=tx, outer_cur=cur):
                raise BlockChainError('Failed to send new tx.')
            db.commit()
            return web_base.json_res({
                'hash': tx.hash.hex(),
                'gas_amount': tx.gas_amount,
                'gas_price': tx.gas_price,
                'fee': tx.gas_amount * tx.gas_price,
                'time': round(time() - start, 3),
                'mint_id': mint_id})
        except Exception:
            return web_base.error_res()


async def change_mint_tx(request):
    start = time()
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        try:
            user_name = post.get('from', C.account2name[C.ANT_UNKNOWN])
            sender = read_name2user(user_name, cur)
            tx = change_mintcoin(
                mint_id=post['mint_id'], cur=cur, amount=post.get('amount'), description=post.get('description'),
                image=post.get('image'), setting=post.get('setting'), new_address=post.get('new_address'),
                sender=sender)
            if not send_newtx(new_tx=tx, outer_cur=cur):
                raise BlockChainError('Failed to send new tx.')
            db.commit()
            return web_base.json_res({
                'hash': tx.hash.hex(),
                'gas_amount': tx.gas_amount,
                'gas_price': tx.gas_price,
                'fee': tx.gas_amount * tx.gas_price,
                'time': round(time() - start, 3)})
        except Exception:
            return web_base.error_res()


__all__ = [
    "create_raw_tx",
    "sign_raw_tx",
    "broadcast_tx",
    "send_from_user",
    "send_many_user",
    "issue_mint_tx",
    "change_mint_tx"
]
