from bc4py.bip32.base58 import *
from bc4py.bip32.bip32 import *
from bc4py.bip32.utils import *

ADDR_SIZE = 1 + 20  # bytes: prefix + identifier
ADDR_STR_SIZE = 34  # str: prefix + identifier + checksum

__all__ = [
    "check_encode",
    "check_decode",
    "Bip32",
    "BIP32_HARDEN",
    "parse_bip32_path",
    "ADDR_SIZE",
    "ADDR_STR_SIZE",
    "is_address",
    "get_address",
    "convert_address",
    "dummy_address",
    "addr2bin",
    "bin2addr",
]


def test():
    from mnemonic import Mnemonic

    words = 'news clever spot drama infant detail sword cover color throw foot primary when slender rhythm clog autumn ecology enough bronze math you modify excuse'
    xprv = 'xprv9s21ZrQH143K3EGRfjQYhZ6fA3HPPiw6rxopHKXfWTrB66evM4fDRiUScJy5RCCGz98nBaCCtwpwFCTDiFG5tx3mdnyyL1MbHmQQ19BWemo'
    xpub = 'xpub661MyMwAqRbcFiLtmkwZ4h3Pi57soBexEBjR5hwH4oP9xtz4tbyTyWnvTb44oGpDbVacdJcga8g26sn7KBYLaerJ54LHqki34DwDq42XRfL'
    language = 'english'

    def test_with_sec():
        # m / purpose' / coin_type' / account' / change / address_index
        path = "m/44'/0'/0'/0/0"
        m = Mnemonic(language)
        seed = m.to_seed(words)
        print("path", path)
        print("seed", seed.hex())
        key = Bip32.from_entropy(seed)
        assert key.extended_key() == xprv
        for n in parse_bip32_path(path):
            key = key.child_key(n)
        assert key.get_public_key().hex() == '03b7d0ce8dd35db0e36ade5e944d03741bb1d181006cfdeaedc8c767aef279b2a5'
        key.dump()

    def test_with_pub():
        path = "m/0/0/0"
        print("path", path)
        key = Bip32.from_extended_key(xpub)
        for n in parse_bip32_path(path):
            key = key.child_key(n)
        key.dump()

    # check at http://bip32.org/
    test_with_sec()
    test_with_pub()


if __name__ == '__main__':
    test()
