#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import V, BlockChainError
from binascii import hexlify, unhexlify
import math

MAX_256_INT = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff


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
        # print("{} = {} + {} / {} / 10.0".format(x, g.x0, height, g.ybnum))
        e = math.exp(-g.c * x)
        # print("{} = math.exp(-{} * {})".format(e, g.c, x))
        r = g.c * math.log(g.b) * e * pow(g.b, e) / g.ybnum / 10.0
        # print("{} = {} * math.log({}) * {} * pow({}, {}) / {} / 10.0".format(r, g.c, g.b, e, g.b, e, g.ybnum))
        # print("round(-{} * {})".format(g.k, r))
        return round(-g.k * r)

    @staticmethod
    def round(i):
        integer = int(i)
        if i - integer >= 0.5:
            return integer + 1
        return integer

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
        g.k = V.BLOCK_ALL_SUPPLY


def bin2signature(b):
    # pk:32, sign:64
    r = list()
    for i in range(len(b) // 96):
        r.append((hexlify(b[i*96:i*96+32]).decode(), b[i*96+32:i*96+96]))
    return r


def signature2bin(s):
    return b''.join([unhexlify(pk.encode())+sign for pk, sign in s])


def bits2target(bits):
    """ Convert bits to target """
    exponent = ((bits >> 24) & 0xff)
    assert 3 <= exponent, "[exponent>=3] but {}.".format(exponent)
    mantissa = bits & 0x7fffff
    if (bits & 0x800000) > 0:
        mantissa *= -1
    return mantissa * pow(256, exponent - 3)


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
