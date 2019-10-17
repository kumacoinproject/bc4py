from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.user import Balance
from bc4py.user.txcreation import *
from bc4py.database.account import *
from bc4py.database.create import create_db
from bc4py.database.tools import get_output_from_input
from bc4py.user.network.sendnew import send_newtx
from bc4py.chain.tx import TX
from bc4py.user.api.utils import error_response
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
    create raw transaction
    * Arguments
        1. **version** :  (numeric, optional, default=__chain_version__)
        2. **type** :     (numeric, optional, default=TRANSFER)
        3. **ntime** :    (numeric, optional, default=NOW)
        4. **deadline** : (numeric, optional, default=NOW+10800)
        5. **inputs** :         (list, optional, default=[])
        6. **outputs** :        (list, optional, default=[])
        7. **gas_price** :      (numeric, optional, default=MINIMUM_PRICE)
        8. **gas_amount** :     (numeric, optional, default=tx_size())
        9. **message_type** :   (numeric, optional, default=MSG_NONE)
        10. **message** :       (numeric, optional, default=None)
    * About
        * time is `unixtime - BLOCK_GENESIS_TIME`
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
    * Arguments
        1. **hex** :        (hex string, required) transaction binary
        2. **signature** :  (list, required) `[(PK, R, S), ..]`
        3. **R** :          (hex string, optional) hash lock transaction
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


async def send_from_user(send: SendOne):
    """
    send tx with single output
    * Arguments
        1. **sender** :       (string, optional, default="@Unknown")  Account name.
        2. **address** :      (string, required)
        3. **coin_id** :      (numeric, optional, default=0)
        4. **amount** :       (numeric, required)
        5. **message_type** : (numeric, optional, default=MSG_NONE)
        6. **message_hex** :  (hex string, optional, default=None) this param disables message and message_type params
        7. **message** :      (string, optional, default=None)
        8. **R** :            (hex string, optional) hash lock transaction
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


async def send_many_user(send: SendMany):
    """
    send with many outputs
    * Arguments
        1. **sender** :     (string, optional, default="@Unknown")  Account name.
        2. **pairs** :    (list, required) `[(address, coin_id, amount), ..]`
        3. **message_type** : (numeric, optional, default=MSG_NONE)
        4. **message_hex** :  (hex string, optional, default=None) this param disables message and message_type params
        5. **message** :      (string, optional, default=None)
        6. **R** :            (hex string, optional) hash lock transaction
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


async def issue_mint_tx(mint: IssueMintFormat):
    """
    issue new mint coin
    * Arguments
        1. **sender** :     (string, optional, default="@Unknown")  Account name.
        2. **name** :       (string, required)   Ex, PyCoin
        3. **unit** :       (string, required)   Ex, PC
        5. **digit** :      (numeric, optional, default=8)
        4. **amount** :     (numeric, required)  minting amount
        6. **description** :      (string, optional, default=None)
        7. **image** :            (string, optional, default=None)  URL of image
        8. **additional_issue** : (string, optional, default=true)
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


async def change_mint_tx(mint: ChangeMintFormat):
    """
    change mint coin settings
    * Arguments
        1. **sender** :       (string, optional, default="@Unknown")  Account name.
        2. **mint_id** :      (numeric, required)  mintcoin's coin_id
        3. **amount** :       (numeric, optional, default=0)  additional mint amount
        4. **description** :  (string, optional, default=None)
        5. **image** :        (string, optional, default=None)  URL of image
        6. **setting** :      (string, optional, default=None)
        7. **new_address** :  (string, optional, default=None)  New owner address
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
