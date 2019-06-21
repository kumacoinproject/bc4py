from bc4py.bip32 import *
from mnemonic import Mnemonic
import unittest


WORDS = 'news clever spot drama infant detail sword cover color throw foot primary when ' \
        'slender rhythm clog autumn ecology enough bronze math you modify excuse'
ROOT_SECRET = 'xprv9s21ZrQH143K3EGRfjQYhZ6fA3HPPiw6rxopHKXfWTrB66evM4fDRiUScJy5RCCGz98' \
              'nBaCCtwpwFCTDiFG5tx3mdnyyL1MbHmQQ19BWemo'
ROOT_PUBLIC = 'xpub661MyMwAqRbcFiLtmkwZ4h3Pi57soBexEBjR5hwH4oP9xtz4tbyTyWnvTb44oGpDbVa' \
              'cdJcga8g26sn7KBYLaerJ54LHqki34DwDq42XRfL'
LANGUAGE = 'english'
HARD_PATH = "m/44'/5'/0'/0/3"
SOFT_PATH = "m/32/12/0/0/3"


def test_parse_and_struct():
    """test bip32 parse and struct path"""
    parsed_path = parse_bip32_path(HARD_PATH)
    struct_path = struct_bip32_path(parsed_path)
    assert HARD_PATH == struct_path


def test_derive_from_secret_key():
    """test derived from private key"""
    bip = Bip32.from_extended_key(ROOT_SECRET)
    assert bip.depth == 0
    assert bip.index == 0
    for i in parse_bip32_path(HARD_PATH):
        bip = bip.child_key(i)
    assert bip.depth == 5
    assert bip.index == 3
    derived_secret = 'xprvA2fdawh3JYy7Zv8oPxTiLhGeyhfC4Gjjq1K2tV2vftYppmma88mW6uUhEP77o4Wgmgr' \
                     'hvJjonaZLRZMcPK11Mjii9N7BcANiBDzS5DN4YWy'
    derived_public = 'xpub6FeyzTDw8vXQnQDGVyzihqDPXjVgTjTbCEEdgsSYEE5oha6ifg5kehoB5fGV8VrWPzv' \
                     '4uJpudNKKfXsg9e4Aj3xYKAin5ChjBA7V3fHoS4z'
    assert bip.extended_key(is_private=True) == derived_secret
    assert bip.extended_key(is_private=False) == derived_public


def test_derive_from_public_key():
    """test derived from public key"""
    bip = Bip32.from_extended_key(ROOT_PUBLIC)
    for i in parse_bip32_path(SOFT_PATH):
        bip = bip.child_key(i)
    derived_public = 'xpub6GNM2dtsy4aM7veEXp7VAhg2n44rHGrqsbvZNz8xASk1qxzFsiocrySaVrJ33cabKCW' \
                     'Ugk3kHBaneBDBFcoD7MPzxfw5oXoeNrFeuMTPZ44'
    assert bip.extended_key(is_private=False) == derived_public


def test_mnemonic_words():
    """test decode mnemonic words and get root secret"""
    m = Mnemonic(LANGUAGE)
    entropy = m.to_seed(WORDS)
    bip = Bip32.from_entropy(entropy)
    assert bip.extended_key(is_private=True) == ROOT_SECRET


if __name__ == "__main__":
    unittest.main()
