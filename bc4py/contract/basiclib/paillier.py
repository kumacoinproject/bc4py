import phe

"""
: use for secret contract
Get keypair
    pk, sk = phe.generate_paillier_keypair()
"""

KEY_LENGTH = phe.paillier.DEFAULT_KEYSIZE // 8
assert KEY_LENGTH == 256, "Default key length is 256, not {}".format(KEY_LENGTH)


def binary2paillier_pk(b):
    """ bytes 2 PaillierPublicKey """
    isinstance(b, bytes)
    n = int.from_bytes(b, 'little')
    return phe.paillier.PaillierPublicKey(n=n)


def paillier_pk2binary(pk):
    """ PaillierPublicKey 2 bytes """
    isinstance(pk, phe.paillier.PaillierPublicKey)
    return pk.n.to_bytes(KEY_LENGTH, 'little')


def binary2encrypted_number(b):
    """ bytes 2 EncryptedNumber """
    isinstance(b, bytes)
    public_key = binary2paillier_pk(b[:KEY_LENGTH])  # 256bytes
    cipher_text = int.from_bytes(b[KEY_LENGTH:KEY_LENGTH*3], 'little')  # 512bytes
    exponent = int.from_bytes(b[KEY_LENGTH*3:KEY_LENGTH*3+1], 'little')  # 1byte
    s = phe.paillier.EncryptedNumber(public_key=public_key, ciphertext=cipher_text, exponent=exponent)
    return s


def encrypted_number2binary(en):
    """ EncryptedNumber 2 bytes """
    isinstance(en, phe.paillier.EncryptedNumber)
    b = paillier_pk2binary(pk=en.public_key)
    b += en.ciphertext().to_bytes(KEY_LENGTH*2, 'little')
    b += en.exponent.to_bytes(1, 'little')
    return b


__price__ = {
    "binary2paillier_pk": 60,
    "paillier_pk2binary": 60,
    "binary2encrypted_number": 60,
    "encrypted_number2binary": 60
}


__all__ = list(__price__)
