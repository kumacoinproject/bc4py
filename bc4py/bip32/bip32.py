#!/usr/bin/env python
#
# Copyright 2014 Corgan Labs
# See LICENSE.txt for distribution terms
#

from bc4py.bip32.base58 import check_decode, check_encode
from bc4py_extension import PyAddress
from fastecdsa.curve import secp256k1
from fastecdsa.util import mod_sqrt
from fastecdsa.point import Point
from fastecdsa.keys import get_public_key
from os import urandom
import hmac
import hashlib
import codecs
import struct

CURVE_GEN = secp256k1.G  # Point class
CURVE_ORDER = secp256k1.q  # int
FIELD_ORDER = secp256k1.p  # int
INFINITY = Point.IDENTITY_ELEMENT  # Point

MIN_ENTROPY_LEN = 128  # bits
BIP32_HARDEN = 0x80000000  # choose from hardened set of child keys
EX_MAIN_PRIVATE = [codecs.decode('0488ade4', 'hex')]  # Version strings for mainnet extended private keys
EX_MAIN_PUBLIC = [codecs.decode('0488b21e', 'hex'),
                  codecs.decode('049d7cb2', 'hex')]  # Version strings for mainnet extended public keys
EX_TEST_PRIVATE = [codecs.decode('04358394', 'hex')]  # Version strings for testnet extended private keys
EX_TEST_PUBLIC = [codecs.decode('043587CF', 'hex')]  # Version strings for testnet extended public keys
WALLET_VERSION = b'\x80'


class Bip32(object):
    __slots__ = ("secret", "public", "chain", "depth", "index", "parent_fpr", "path")

    def __init__(self, secret, public, chain, depth, index, fpr, path):
        self.secret: int = secret
        self.public: Point = public
        self.chain: bytes = chain
        self.depth: int = depth
        self.index: int = index
        self.parent_fpr: bytes = fpr
        self.path: str = path

    def __repr__(self):
        key_type = "PUB" if self.secret is None else "SEC"
        return "<BIP32-{} depth={} path={}>".format(key_type, self.depth, self.path)

    @classmethod
    def from_entropy(cls, entropy, is_public=False):
        """Create a BIP32Key using supplied entropy >= MIN_ENTROPY_LEN"""
        if entropy is None:
            entropy = urandom(MIN_ENTROPY_LEN // 8)  # Python doesn't have os.random()
        if not len(entropy) >= MIN_ENTROPY_LEN // 8:
            raise ValueError("Initial entropy %i must be at least %i bits" % (len(entropy), MIN_ENTROPY_LEN))
        i64 = hmac.new(b"Bitcoin seed", entropy, hashlib.sha512).digest()
        il, ir = i64[:32], i64[32:]
        # FIXME test Il for 0 or less than SECP256k1 prime field order
        secret = int.from_bytes(il, 'big')
        public = get_public_key(secret, secp256k1)
        if is_public:
            return cls(secret=None, public=public, chain=ir, depth=0, index=0, fpr=b'\0\0\0\0', path='m')
        else:
            return cls(secret=secret, public=public, chain=ir, depth=0, index=0, fpr=b'\0\0\0\0', path='m')

    @classmethod
    def from_extended_key(cls, key, is_public=False):
        """
        Create a BIP32Key by importing from extended private or public key string
        If public is True, return a public-only key regardless of input type.
        """
        # Sanity checks
        if isinstance(key, str):
            raw = check_decode(key)
        else:
            raw = b'\x00\x00\x00\x00' + key
        if len(raw) != 78:
            raise ValueError("extended key format wrong length")

        # Verify address version/type
        version = raw[:4]
        if version == b'\x00\x00\x00\x00':
            is_testnet = None
            is_pubkey = None
        elif version in EX_MAIN_PRIVATE:
            is_testnet = False
            is_pubkey = False
        elif version in EX_TEST_PRIVATE:
            is_testnet = True
            is_pubkey = False
        elif version in EX_MAIN_PUBLIC:
            is_testnet = False
            is_pubkey = True
        elif version in EX_TEST_PUBLIC:
            is_testnet = True
            is_pubkey = True
        else:
            raise ValueError("unknown extended key version")

        # Extract remaining fields
        depth = raw[4]
        fpr = raw[5:9]
        child = struct.unpack(">L", raw[9:13])[0]
        chain = raw[13:45]
        data = raw[45:78]

        # check prefix of key
        is_pubkey = (data[0] == 2 or data[0] == 3)

        # Extract private key or public key point
        if not is_pubkey:
            secret = int.from_bytes(data[1:], 'big')
            public = get_public_key(secret, secp256k1)
        else:
            # Recover public curve point from compressed key
            # Python3 FIX
            lsb = data[0] & 1 if type(data[0]) == int else ord(data[0]) & 1
            x = int.from_bytes(data[1:], 'big')
            ys = (x**3 + 7) % FIELD_ORDER  # y^2 = x^3 + 7 mod p
            y, _ = mod_sqrt(ys, FIELD_ORDER)
            if y & 1 != lsb:
                y = FIELD_ORDER - y
            secret = None
            public = Point(x, y, secp256k1)

        if not is_pubkey and is_public:
            return cls(secret=None, public=public, chain=chain, depth=depth, index=child, fpr=fpr, path='m')
        else:
            return cls(secret=secret, public=public, chain=chain, depth=depth, index=child, fpr=fpr, path='m')

    # Internal methods not intended to be called externally
    def _hmac(self, data):
        """
        Calculate the HMAC-SHA512 of input data using the chain code as key.
        Returns a tuple of the left and right halves of the HMAC
        """
        i64 = hmac.new(self.chain, data, hashlib.sha512).digest()
        return i64[:32], i64[32:]

    def CKDpriv(self, i):
        """
        Create a child key of index 'i'.

        If the most significant bit of 'i' is set, then select from the
        hardened key set, otherwise, select a regular child key.

        Returns a BIP32Key constructed with the child key parameters,
        or None if i index would result in an invalid key.
        """

        # Index as bytes, BE
        i_str = struct.pack(">L", i)

        # Data to HMAC
        if i & BIP32_HARDEN:
            data = b'\0' + self.get_private_key() + i_str
            path = self.path + '/' + str(i % BIP32_HARDEN) + '\''
        else:
            data = self.get_public_key() + i_str
            path = self.path + '/' + str(i)
        # Get HMAC of data
        (Il, Ir) = self._hmac(data)

        # Construct new key material from Il and current private key
        Il_int = int.from_bytes(Il, 'big')
        if Il_int > CURVE_ORDER:
            return None
        k_int = (Il_int + self.secret) % CURVE_ORDER
        if k_int == 0:
            return None

        # Construct and return a new BIP32Key
        public = get_public_key(k_int, secp256k1)
        return Bip32(
            secret=k_int, public=public, chain=Ir, depth=self.depth + 1, index=i, fpr=self.fingerprint(), path=path)

    def CKDpub(self, i):
        """
        Create a publicly derived child key of index 'i'.

        If the most significant bit of 'i' is set, this is
        an error.

        Returns a BIP32Key constructed with the child key parameters,
        or None if index would result in invalid key.
        """

        if i & BIP32_HARDEN:
            raise Exception("Cannot create a hardened child key using public child derivation")

        # Data to HMAC.  Same as CKDpriv() for public child key.
        data = self.get_public_key() + struct.pack(">L", i)

        # Get HMAC of data
        (Il, Ir) = self._hmac(data)

        # Construct curve point Il*G+K
        Il_int = int.from_bytes(Il, 'big')
        if Il_int >= CURVE_ORDER:
            return None
        point = Il_int*CURVE_GEN + self.public
        if point == INFINITY:
            return None

        # Construct and return a new BIP32Key
        path = self.path + '/' + str(i)
        return Bip32(
            secret=None, public=point, chain=Ir, depth=self.depth + 1, index=i, fpr=self.fingerprint(), path=path)

    def child_key(self, i):
        """
        Create and return a child key of this one at index 'i'.

        The index 'i' should be summed with BIP32_HARDEN to indicate
        to use the private derivation algorithm.
        """
        if self.secret is None:
            return self.CKDpub(i)
        else:
            return self.CKDpriv(i)

    def get_private_key(self):
        if self.secret is None:
            raise Exception("Publicly derived deterministic keys have no private half")
        else:
            return self.secret.to_bytes(32, 'big')

    def get_public_key(self):
        x = self.public.x.to_bytes(32, 'big')
        if self.public.y & 1:
            return b'\3' + x
        else:
            return b'\2' + x

    def get_address(self, hrp, ver):
        """Return bech32 compressed address"""
        return PyAddress.from_param(hrp, ver, self.identifier())

    def identifier(self):
        """Return key identifier as string"""
        pk = self.get_public_key()
        return hashlib.new('ripemd160', hashlib.sha256(pk).digest()).digest()

    def fingerprint(self):
        """Return key fingerprint as string"""
        return self.identifier()[:4]

    def extended_key(self, is_private=True, encoded=True, is_testnet=False):
        """Return extended private or public key as string, optionally base58 encoded"""
        if self.secret is None and is_private is True:
            raise Exception("Cannot export an extended private key from a public-only deterministic key")
        if is_testnet:
            version = EX_TEST_PRIVATE[0] if is_private else EX_TEST_PUBLIC[0]
        else:
            version = EX_MAIN_PRIVATE[0] if is_private else EX_MAIN_PUBLIC[0]
        depth = self.depth.to_bytes(1, 'big')
        fpr = self.parent_fpr
        child = struct.pack('>L', self.index)
        chain = self.chain
        if self.secret is None or is_private is False:
            # startswith b'\x02' or b'\x03'
            data = self.get_public_key()
        else:
            # startswith b'\x00'
            data = b'\x00' + self.get_private_key()
        if encoded:
            return check_encode(version + depth + fpr + child + chain + data)
        else:
            return depth + fpr + child + chain + data

    def wallet_import_format(self, prefix=WALLET_VERSION):
        """Returns private key encoded for wallet import"""
        if self.secret is None:
            raise Exception("Publicly derived deterministic keys have no private half")
        raw = prefix + self.get_private_key() + b'\x01'  # Always compressed
        return check_encode(raw)

    def dump(self):
        """Dump key fields mimicking the BIP0032 test vector format"""
        print("   * Identifier")
        print("     * (hex):      ", self.identifier().hex())
        print("     * (fpr):      ", self.fingerprint().hex())
        print("     * (main addr):", self.get_address('bc', 0))
        print("     * (path):     ", self.path)
        if self.secret:
            print("   * Secret key")
            print("     * (hex):      ", self.get_private_key().hex())
            print("     * (wif):      ", self.wallet_import_format())

        print("   * Public key")
        print("     * (hex):      ", self.get_public_key().hex())
        print("   * Chain code")
        print("     * (hex):      ", self.chain.hex())
        print("   * Serialized")
        print("     * (pub hex):  ", self.extended_key(is_private=False, encoded=False).hex())
        print("     * (pub b58):  ", self.extended_key(is_private=False, encoded=True))
        if self.secret:
            print("     * (prv hex):  ", self.extended_key(is_private=True, encoded=False).hex())
            print("     * (prv b58):  ", self.extended_key(is_private=True, encoded=True))


def parse_bip32_path(path):
    """parse BIP32 format"""
    r = list()
    for s in path.split('/'):
        if s == 'm':
            continue
        elif s.endswith("'") or s.endswith('h'):
            r.append(int(s[:-1]) + BIP32_HARDEN)
        else:
            r.append(int(s))
    return r


def struct_bip32_path(path):
    """struct BIP32 string path"""
    s = 'm'
    for p in path:
        if p & BIP32_HARDEN:
            s += "/{}'".format(p % BIP32_HARDEN)
        else:
            s += "/{}".format(p)
    return s


__all__ = [
    "BIP32_HARDEN",
    "Bip32",
    "parse_bip32_path",
    "struct_bip32_path",
]
