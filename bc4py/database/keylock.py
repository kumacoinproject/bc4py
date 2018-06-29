from bc4py.config import V, BlockChainError
from bc4py.utils import AESCipher
from nem_ed25519.key import public_key
from nem_ed25519.base import Encryption
from binascii import hexlify


def is_locked_database(cur):
    d = cur.execute("SELECT `sk`,`pk` FROM `pool` LIMIT 1").fetchone()
    if d is None:
        return False  # Unlocked
    sk, pk = d
    try:
        sk = AESCipher.decrypt(V.ENCRYPT_KEY, sk) if V.ENCRYPT_KEY else sk
        sk = hexlify(sk).decode()
    except ValueError:
        return True
    if len(sk) != 64:
        return True
    elif public_key(sk) == hexlify(pk).decode():
        return False  # Unlocked
    else:
        return True


def change_encrypt_key(new_key, cur):
    # SecretKeyの鍵を変更する、Noneの場合は非暗号化
    d = cur.execute("SELECT `id`, `sk`, `pk` FROM `pool`").fetchall()
    updates = list()
    ecc = Encryption(prefix=V.BLOCK_PREFIX)
    for uuid, sk, pk in d:
        sk = AESCipher.decrypt(V.ENCRYPT_KEY, sk) if V.ENCRYPT_KEY else sk
        sk = hexlify(sk).decode()
        ecc.public_key(sk=sk)
        if ecc.pk != hexlify(pk).decode():
            raise BlockChainError('Decryption error! wrong key. [{}=>{}]'
                                  .format(hexlify(ecc.pk).decode(), hexlify(pk).decode()))
        new_sk = sk if new_key is None else AESCipher.encrypt(key=new_key, raw=sk)
        updates.append((uuid, new_sk))
    cur.executemany("""
        UPDATE `pool` SET `sk`=? WHERE `id`=?
        """, updates)


__all__ = [
    "is_locked_database",
    "change_encrypt_key",
]
