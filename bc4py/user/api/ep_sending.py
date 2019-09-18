from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.user import Balance
from bc4py.user.txcreation import *
from bc4py.database.account import *
from bc4py.database.create import create_db
from bc4py.database.tools import get_output_from_input
from bc4py.user.network.sendnew import send_newtx
from bc4py.chain.tx import TX
from bc4py.user.api.utils import auth, error_response
from fastapi import Depends
from fastapi.security import HTTPBasicCredentials
from pydantic import BaseModel
from typing import List, Dict, Tuple
from bc4py_extension import PyAddress
from binascii import a2b_hex
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


class SendOne(BaseModel):
    address: str
    amount: int
    coin_id: int = 0
    sender: str = C.account2name[C.ANT_UNKNOWN]
    message_type: int = C.MSG_NONE
    message_hex: str = None
    message: str = None
    R: str = None


class SendMany(BaseModel):
    sender: str = C.account2name[C.ANT_UNKNOWN]
    pairs: List[Tuple[(str, int, int)]]
    message_type: int = C.MSG_NONE
    message_hex: str = None
    message: str = None
    R: str = None


class RawTransaction(BaseModel):
    version: int = __chain_version__
    type: int = C.TX_TRANSFER
    ntime: int = None
    deadline: int = None
    inputs: List[Tuple[(str, int)]]
    outputs: List[Tuple[(str, int, int)]]
    gas_price: int = V.COIN_MINIMUM_PRICE
    gas_amount: int = None
    message_type: int = C.MSG_NONE
    message: str = ''


class BroadcastFormat(BaseModel):
    hex: str
    signature: List[List[str]]
    R: str = None


class IssueMintFormat(BaseModel):
    sender: str = C.account2name[C.ANT_UNKNOWN]
    name: str
    unit: str
    digit: int = 8
    amount: int
    description: str = None
    image: str = None
    additional_issue: bool = True


class ChangeMintFormat(BaseModel):
    sender: str = C.account2name[C.ANT_UNKNOWN]
    mint_id: int
    amount: int = None
    description: str = None
    image: str = None
    additional_issue: bool = True
    setting: Dict[str, bool] = None
    new_address: str = None


async def create_raw_tx(raw: RawTransaction):
    """
    create raw transaction with parameters.
    # [version=1] [type=TRANSFER] [ntime=now] [deadline=now+10800]
    # [inputs:list()] [outputs:list()]
    # [gas_price=MINIMUM_PRICE] [gas_amount=MINIMUM_AMOUNT]
    # [message_type=None] [message=None]
    """
    try:
        if raw.ntime is None:
            raw.ntime = int(time() - V.BLOCK_GENESIS_TIME)
        if raw.deadline is None:
            raw.deadline = raw.ntime + 10800
        raw.message = type2message(raw.message_type, raw.message)
        inputs = list()
        input_address = set()
        for txhash, txindex in raw.inputs:
            txhash = a2b_hex(txhash)
            inputs.append((txhash, txindex))
            pair = get_output_from_input(txhash, txindex)
            if pair is None:
                return error_response("input is unknown or already used")
            address, coin_id, amount = pair
            input_address.add(address)
        outputs = list()
        for address, coin_id, amount in raw.outputs:
            outputs.append((PyAddress.from_string(address), coin_id, amount))
        tx = TX.from_dict(
            tx={
                'version': raw.version,
                'type': raw.type,
                'time': raw.ntime,
                'deadline': raw.deadline,
                'inputs': inputs,
                'outputs': outputs,
                'gas_price': raw.gas_price,
                'gas_amount': 0,
                'message_type': raw.message_type,
                'message': raw.message
            })
        if raw.gas_amount is None:
            tx.gas_amount = tx.size + len(input_address) * C.SIGNATURE_GAS
        else:
            tx.gas_amount = raw.gas_amount
        tx.serialize()
        return {
            'tx': tx.getinfo(),
            'hex': tx.b.hex(),
        }
    except Exception:
        return error_response()


async def broadcast_tx(data: BroadcastFormat):
    """
    broadcast raw transaction
    * hex
        * type: string hex
        * required: true
        * example: "020000000300000022fd0300522704006400000000000000270000000000000000000000000000"
        * description: "raw transaction hex string"
    * signature
        * type: array
        * required: true
        * example: [["0361720a316acb547a3da8c1de0b307dc2e6e977ac04fd4cea31054d8571bfc06d", "9abac1bdc65b87502ee58d71885be9aa3ef2c2ea0162f86f9572e5410c8a8c21", "e8159d3b4c77878bd9f9b3efac0fb9a8cc9457fd4a40499f9200c94253a4061d"]]
        * description: "[[PK, R, S], ..]"
    * R
        * type: string hex
        * required: true
        * description: hash lock transaction
    """
    start = time()
    try:
        binary = a2b_hex(data.hex)
        new_tx = TX.from_binary(binary=binary)
        for sign in data.signature:
            new_tx.signature.append(
                tuple(map(a2b_hex, sign))
            )
        if data.R is not None:
            new_tx.R = a2b_hex(data.R)
        with create_db(V.DB_ACCOUNT_PATH, strict=True) as db:
            cur = await db.cursor()
            if not await send_newtx(new_tx=new_tx, cur=cur):
                raise BlockChainError('Failed to send new tx')
            await db.commit()
        return {
            'hash': new_tx.hash.hex(),
            'gas_amount': new_tx.gas_amount,
            'gas_price': new_tx.gas_price,
            'fee': new_tx.gas_amount * new_tx.gas_price,
            'time': round(time() - start, 3),
        }
    except Exception:
        return error_response()


async def send_from_user(send: SendOne, credentials: HTTPBasicCredentials = Depends(auth)):
    """
    send with single output
    * from
        * type: string,
        * required: false
        * example: "@Unknown"
        * description: "sending account name"
    * address:
        * type: string
        * required: true
        * example: ""
    * coin_id:
        * type: integer
        * required: false
        * example: 0
    * amount:
        * type: integer
        * required: true
        * example: 1000
    * message:
        * type: string
        * required: false
        * example: ""
        * message_type:
        * type: integer
        * required: false
        * example: 0
        * description: "MSG_PLAIN"
    * hex:
        * type: string
        * required: false
        * example: "null"
        * description: "this param disables message and message_type params"
    """
    start = time()
    async with create_db(V.DB_ACCOUNT_PATH, strict=True) as db:
        cur = await db.cursor()
        try:
            from_id = await read_name2userid(send.sender, cur)
            to_address = PyAddress.from_string(send.address)
            coins = Balance(send.coin_id, send.amount)
            if send.message_hex is not None:
                send.message_type = C.MSG_BYTE
                send.message = a2b_hex(send.message_hex)
            elif send.message is not None:
                if send.message_type is None:
                    send.message_type = C.MSG_PLAIN
                send.message = type2message(send.message_type, send.message)
            else:
                send.message_type = C.MSG_NONE
                send.message = b''
            new_tx = await send_from(
                from_id, to_address, coins, cur,
                msg_type=send.message_type, msg_body=send.message)
            if send.R:
                new_tx.R = a2b_hex(send.R)
            if not await send_newtx(new_tx=new_tx, cur=cur):
                raise BlockChainError('Failed to send new tx')
            await db.commit()
            return {
                'hash': new_tx.hash.hex(),
                'gas_amount': new_tx.gas_amount,
                'gas_price': new_tx.gas_price,
                'fee': new_tx.gas_amount * new_tx.gas_price,
                'time': round(time() - start, 3),
            }
        except Exception:
            return error_response()


async def send_many_user(send: SendMany, credentials: HTTPBasicCredentials = Depends(auth)):
    """
    send with many outputs
    """
    start = time()
    async with create_db(V.DB_ACCOUNT_PATH, strict=True) as db:
        cur = await db.cursor()
        try:
            user_id = await read_name2userid(send.sender, cur)
            send_pairs = list()
            for address, coin_id, amount in send.pairs:
                send_pairs.append((PyAddress.from_string(address), int(coin_id), int(amount)))
            if send.message_hex is not None:
                send.message_type = C.MSG_BYTE
                send.message = a2b_hex(send.message_hex)
            elif send.message is not None:
                if send.message_type is None:
                    send.message_type = C.MSG_PLAIN
                send.message = type2message(send.message_type, send.message)
            else:
                send.message_type = C.MSG_NONE
                send.message = b''
            new_tx = await send_many(
                user_id, send_pairs, cur,
                msg_type=send.message_type, msg_body=send.message)
            if not await send_newtx(new_tx=new_tx, cur=cur):
                raise BlockChainError('Failed to send new tx')
            await db.commit()
            return {
                'hash': new_tx.hash.hex(),
                'gas_amount': new_tx.gas_amount,
                'gas_price': new_tx.gas_price,
                'fee': new_tx.gas_amount * new_tx.gas_price,
                'time': round(time() - start, 3),
            }
        except Exception:
            return error_response()


async def issue_mint_tx(mint: IssueMintFormat, credentials: HTTPBasicCredentials = Depends(auth)):
    """
    issue minting new coin
    """
    start = time()
    async with create_db(V.DB_ACCOUNT_PATH, strict=True) as db:
        cur = await db.cursor()
        try:
            sender = await read_name2userid(mint.sender, cur)
            mint_id, tx = await issue_mint_coin(
                name=mint.name,
                unit=mint.unit,
                digit=mint.digit,
                amount=mint.amount,
                cur=cur,
                description=mint.description,
                image=mint.image,
                additional_issue=mint.additional_issue,
                sender=sender)
            if not await send_newtx(new_tx=tx, cur=cur):
                raise BlockChainError('Failed to send new tx')
            await db.commit()
            return {
                'hash': tx.hash.hex(),
                'gas_amount': tx.gas_amount,
                'gas_price': tx.gas_price,
                'fee': tx.gas_amount * tx.gas_price,
                'time': round(time() - start, 3),
                'mint_id': mint_id,
            }
        except Exception:
            return error_response()


async def change_mint_tx(mint: ChangeMintFormat, credentials: HTTPBasicCredentials = Depends(auth)):
    """
    change mint coin settings
    """
    start = time()
    async with create_db(V.DB_ACCOUNT_PATH, strict=True) as db:
        cur = await db.cursor()
        try:
            sender = await read_name2userid(mint.sender, cur)
            tx = await change_mint_coin(
                mint_id=mint.mint_id,
                cur=cur,
                amount=mint.amount,
                description=mint.description,
                image=mint.image,
                setting=mint.setting,
                new_address=mint.new_address,
                sender=sender)
            if not await send_newtx(new_tx=tx, cur=cur):
                raise BlockChainError('Failed to send new tx')
            await db.commit()
            return {
                'hash': tx.hash.hex(),
                'gas_amount': tx.gas_amount,
                'gas_price': tx.gas_price,
                'fee': tx.gas_amount * tx.gas_price,
                'time': round(time() - start, 3),
            }
        except Exception:
            return error_response()


__all__ = [
    "create_raw_tx",
    "broadcast_tx",
    "send_from_user",
    "send_many_user",
    "issue_mint_tx",
    "change_mint_tx",
]
