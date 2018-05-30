#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py import __chain_version__
from bc4py.chain.utils import bits2target
from bc4py.config import C, V, BlockChainError
from hashlib import sha256
from binascii import hexlify
import time
import struct


class TX:
    __slots__ = (
        "b", "hash", "height", "pos_amount",
        "version", "type", "time", "deadline", "inputs", "outputs",
        "gas_price", "gas_amount", "message_type", "message",
        "signature", "used_index", "meta",
        "__weakref__")

    def __repr__(self):
        return "<TX {} {} {} >"\
            .format(self.height, C.txtype2name[self.type], hexlify(self.hash).decode())

    def __init__(self, binary=None, tx=None):
        self.b = None
        # tx id
        self.hash = None
        self.height = None
        # pos
        self.pos_amount = None
        # tx body
        self.version = None  # 4bytes int
        self.type = None  # 4bytes int
        self.time = None  # 4bytes int
        self.deadline = None  # 4bytes int
        self.inputs = None  # [(txhash, txindex),..]
        self.outputs = None  # [(address, coin_id, amount),..]
        self.gas_price = None  # fee
        self.gas_amount = None  # fee
        self.message_type = None  # 2bytes int
        self.message = None  # 0~256**4 bytes bin
        # proof
        self.signature = None  # [(pubkey, signature),.. ]
        self.used_index = None
        # 処理には使わないが有用なデータ
        self.meta = dict()

        if binary:
            self.b = binary
            self.deserialize()
        elif tx:
            self.version = tx.get('version', __chain_version__)
            self.type = tx['type']
            self.time = tx['time']
            self.deadline = tx['deadline']
            self.inputs = tx['inputs']
            self.outputs = tx['outputs']
            self.gas_price = tx['gas_price']
            self.gas_amount = tx['gas_amount']
            self.message_type = tx['message_type']
            self.message = tx['message']
            self.serialize()
        self.signature = list()
        self.used_index = b''

    def serialize(self):
        self.b = struct.pack('>4I', self.version, self.type, self.time, self.deadline)
        # inputs
        self.b += len(self.inputs).to_bytes(1, 'big')
        for txhash, txindex in self.inputs:
            self.b += struct.pack('>32sB', txhash, txindex)
        # outputs
        self.b += len(self.outputs).to_bytes(1, 'big')
        for address, coin_id, amount in self.outputs:
            self.b += struct.pack('>40sIQ', address.encode(), coin_id, amount)
        # fee, message
        self.b += struct.pack('>QQHI', self.gas_price, self.gas_amount, self.message_type, len(self.message))
        self.b += self.message
        # txhash
        self.hash = sha256(self.b).digest()

    def deserialize(self):
        self.version, self.type, self.time, self.deadline = struct.unpack_from('>4I', self.b, 0)
        # inputs
        pos = 16
        inputs_num = int.from_bytes(self.b[pos:pos+1], 'big')
        pos += 1
        self.inputs = list()
        add_pos = struct.calcsize('>32sB')
        for i in range(inputs_num):
            self.inputs.append(struct.unpack_from('>32sB', self.b, pos))
            pos += add_pos
        # outputs
        outputs_num = int.from_bytes(self.b[pos:pos+1], 'big')
        pos += 1
        self.outputs = list()
        add_pos = struct.calcsize('>40sIQ')
        for i in range(outputs_num):
            address, coin_id, amount = struct.unpack_from('>40sIQ', self.b, pos)
            self.outputs.append((address.decode(), coin_id, amount))
            pos += add_pos
        # fee, message
        self.gas_price, self.gas_amount, self.message_type, message_len = \
            struct.unpack_from('>QQHI', self.b, pos)
        pos += struct.calcsize('>QQHI')
        self.message = self.b[pos:pos+message_len]
        pos += message_len
        if len(self.b) != pos:
            raise BlockChainError('Do not match len %d!=%d' % (len(self.b), pos))
        self.hash = sha256(self.b).digest()

    def getinfo(self):
        r = dict()
        r['hash'] = hexlify(self.hash).decode()
        r['pos_amount'] = self.pos_amount
        r['height'] = self.height
        r['version'] = self.version
        r['type'] = C.txtype2name[self.type]
        r['time'] = self.time + V.BLOCK_GENESIS_TIME
        r['deadline'] = self.deadline + V.BLOCK_GENESIS_TIME
        r['inputs'] = [(hexlify(txhash).decode(), txindex) for txhash, txindex in self.inputs]
        r['outputs'] = self.outputs
        r['gas_price'] = self.gas_price
        r['gas_amount'] = self.gas_amount
        r['message_type'] = C.msgtype2name[self.message_type] if self.message_type in C.msgtype2name else self.message_type
        r['message'] = self.message.decode() if self.message_type == C.MSG_PLAIN else hexlify(self.message).decode()
        r['signature'] = [(pubkey, hexlify(signature).decode()) for pubkey, signature in self.signature]
        r['meta'] = self.meta
        return r

    def getsize(self):
        s = len(self.b)
        for pk, sign in self.signature:
            assert isinstance(pk, str), 'pk is str.'
            assert isinstance(sign, bytes), 'sign is bytes'
            s += len(pk) // 2 + len(sign)
        return s

    def get_pos_hash(self, previous_hash, pos_bias):
        # staked => sha256(txhash + previous_hash) / amount < 256^32 / diff
        pos_work_hash = sha256(self.hash + previous_hash).digest()
        work = int.from_bytes(pos_work_hash, 'big')
        work //= self.pos_amount
        work *= bits2target(pos_bias)
        return work.to_bytes(32, 'big')

    def pos_check(self, previous_hash, pos_bias, pos_target_hash):
        # staked => sha256(txhash + previous_hash) / amount < 256^32 / diff
        pos_work_hash = sha256(self.hash + previous_hash).digest()
        work = int.from_bytes(pos_work_hash, 'big')
        work //= self.pos_amount
        work *= bits2target(pos_bias)
        return work < int.from_bytes(pos_target_hash, 'big')

    def update_time(self, retention=10800):
        if retention < 10800:
            raise BlockChainError('Retention time is too short.')
        now = int(time.time())
        self.time = now - V.BLOCK_GENESIS_TIME
        self.deadline = now - V.BLOCK_GENESIS_TIME + retention
        self.serialize()

"""
'version'
'type'
'time'
'deadline'
'inputs'
'outputs'
'gas_price'
'gas_amount'
'message_type'
'message'
"""