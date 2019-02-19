from io import BytesIO
from hashlib import sha512

"""Proof of capacity hash functions
1. generate hashes
seed0 = [address 40bytes]-[nonce 4bytes]
hash0 = SHA512(seed0)
seed1 = [address 40bytes]-[nonce 4bytes]-[hash0]
hash1 = SHA512(seed1)
...
seed63 = [address 40bytes]-[nonce 4bytes]-...-[hash62]
hash63 = SHA512(seed63)
finalHash = SHA512(seed63 + hash63)

2. all hashes XOR with finalHash
hash'N = hashN ^ finalHash

3. select specific hash by previousHash
32bytes binary to integer little endian -> previousInt
div previousInt by 128 and get remainder -> previousRemainder
and div previousRemainder by 2 and get q(quotient) and r(remainder)
get hash'(q), former if r=0 or latter if r=1

4. verify block
workHash = SHA256(blockTime + hash'(q) + BlockHeight)
verified by "workHash < targetHash"
"""


def create_poc_hashes(b_address, nonce):
    # 64x64=4096bytes
    bio = BytesIO()
    bio.write(b_address + nonce)
    hashes = list()
    # create 64bytes 64 hash list
    for _ in range(64):
        hashed = sha512(bio.getvalue()).digest()
        hashes.append(hashed)
        bio.write(hashed)
    final = int.from_bytes(sha512(bio.getvalue()).digest(), 'little')
    bio.close()
    return final, hashes


def poc_hash_iter(b_address, nonce):
    bio = BytesIO()
    bio.write(b_address + nonce)
    hashes = list()
    # create 64bytes 64 hash list
    for _ in range(64):
        hashed = sha512(bio.getvalue()).digest()
        hashes.append(hashed)
        bio.write(hashed)
    final = int.from_bytes(sha512(bio.getvalue()).digest(), 'little')
    bio.close()
    # XOR by final hash
    for s in hashes:
        yield (final ^ int.from_bytes(s, 'little')).to_bytes(64, 'little')


def get_poc_hash(b_address, nonce, previous_hash):
    bio = BytesIO()
    bio.write(b_address + nonce)
    hashes = list()
    for _ in range(64):
        hashed = sha512(bio.getvalue()).digest()
        hashes.append(hashed)
        bio.write(hashed)
    final = int.from_bytes(sha512(bio.getvalue()).digest(), 'little')
    bio.close()
    # get scope index
    q, r = divmod(int.from_bytes(previous_hash, 'little') % 128, 2)
    # XOR by final hash
    h = (final ^ int.from_bytes(hashes[q], 'little')).to_bytes(64, 'little')
    # former or latter
    if r == 0:
        return h[:32]
    else:
        return h[32:]


__all__ = [
    "create_poc_hashes",
    "poc_hash_iter",
    "get_poc_hash",
]
