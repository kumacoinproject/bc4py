import msgpack
import math

DEFAULT_TARGET = float(0x00000000ffff0000000000000000000000000000000000000000000000000000)


class GompertzCurve(object):
    k = None  # total block reward supply
    b = 0.4
    c = 3.6
    ybnum = float(365 * 24 * 60)
    x0 = -0.4

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
    def base_total_supply():
        g = GompertzCurve
        e = math.exp(-g.c * g.x0)
        return round(g.k * (g.b**e)) - g.calc_block_reward(0)

    @staticmethod
    def calc_total_supply(height):
        g = GompertzCurve
        x = g.x0 + height / g.ybnum / 10.0
        e = math.exp(-g.c * x)
        return round(g.k * (g.b**e)) - g.base_total_supply()


def bin2signature(b):
    # pk:33, r:32or33 s: 32
    # b = BytesIO(b)
    # d = list(msgpack.Unpacker(b, raw=True, use_list=False, encoding='utf8'))
    # return d
    return list(msgpack.unpackb(b, raw=True, use_list=False, encoding='utf8'))


def signature2bin(s):
    # b = BytesIO()
    # for pk, r, s in s:
    #    b.write(msgpack.packb((pk, r, s), use_bin_type=True))
    # return b.getvalue()
    return msgpack.packb(s, use_bin_type=True)


def bits2target(bits):
    """ Convert bits to target """
    exponent = ((bits >> 24) & 0xff)
    assert 3 <= exponent, "[exponent>=3] but {}".format(exponent)
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


__all__ = [
    "DEFAULT_TARGET",
    "GompertzCurve",
    "bin2signature",
    "signature2bin",
    "bits2target",
    "target2bits",
]
