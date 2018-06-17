#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import V, BlockChainError
from binascii import hexlify, unhexlify
import math

MAX_256_INT = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff


#def calc_block_reward(height):
#    span = V.BLOCK_HALVING_SPAN // V.BLOCK_TIME_SPAN
#    reward = V.BLOCK_REWARD
#    height -= span
#    while height > 0:
#        height -= span
#        reward >>= 1
#    return reward


class GompertzCurve:
    k = None  # total block reward supply
    b = 0.4
    c = 2.0
    ybnum = float(365 * 24 * 60)
    x0 = -0.6

    @staticmethod
    def calc_block_reward(height):
        g = GompertzCurve
        x = g.x0 + height / g.ybnum / 10.0
        e = math.exp(-g.c * x)
        r = -g.k * g.c * math.log(g.b) * e * pow(g.b, e) / g.ybnum / 10.0
        return round(r) if 0 < r else 0

    @staticmethod
    def base_total_supply():
        g = GompertzCurve
        e = math.exp(-g.c * g.x0)
        return round(g.k * (g.b ** e)) - g.calc_block_reward(0)

    @staticmethod
    def calc_total_supply(height):
        g = GompertzCurve
        x = g.x0 + height / g.ybnum / 10.0
        e = math.exp(-g.c * x)
        return round(g.k * (g.b ** e)) - g.base_total_supply()

    @staticmethod
    def setup_params():
        g = GompertzCurve
        g.k = V.BLOCK_REWARD * (V.BLOCK_HALVING_SPAN // V.BLOCK_TIME_SPAN) * 2


def bin2signature(b):
    # pk:32, sign:64
    r = list()
    for i in range(len(b) // 96):
        r.append((hexlify(b[i*96:i*96+32]).decode(), b[i*96+32:i*96+96]))
    return r


def signature2bin(s):
    return b''.join([unhexlify(pk.encode())+sign for pk, sign in s])


def bits2target(bits):
    bitsN = (bits >> 24) & 0xff
    if bitsN < 0x03 or bitsN > 0x1f:
        print(hex(bits))
        raise BaseException("First part of bits should be in [0x03, 0x1f] {}".format(hex(bitsN)))  # d=>f
    bitsBase = bits & 0xffffff
    if bitsBase < 0x008000 or bitsBase > 0x7fffff:
        print(hex(bits))
        raise BaseException("Second part of bits should be in [0x008000, 0x7fffff] {}".format(hex(bitsBase)))
    return bitsBase << (8 * (bitsN - 3))


def target2bits(target):
    s = ("%064x" % target)[2:]
    while s[:2] == '00' and len(s) > 6:
        s = s[2:]
    bitsN, bitsBase = len(s) // 2, int('0x' + s[:6], 16)
    if bitsBase >= 0x800000:
        bitsN += 1
        bitsBase >>= 8
    return bitsN << 24 | bitsBase


def check_output_format(outputs):
    for o in outputs:
        if not isinstance(o, tuple):
            raise BlockChainError('Outputs is tuple.')
        elif len(o) != 3:
            raise BlockChainError('Output is three element.')
        address, coin_id, amount = o
        if not isinstance(address, str) or len(address) != 40:
            raise BlockChainError('output address is 40 string. {}'.format(address))
        elif not isinstance(coin_id, int) or coin_id < 0:
            raise BlockChainError('output coin_id is 0< int. {}'.format(coin_id))
        elif not isinstance(amount, int) or not(amount > 0):
            raise BlockChainError('output amount is 0<= int. {}'.format(amount))
