# from bc4py.chain.difficulty import get_bits_by_hash
from bc4py.config import C
from bc4py.user.generate import confirmed_generating_block
from binascii import hexlify, unhexlify
from os import urandom
from time import time
from logging import getLogger


log = getLogger('bc4py')
base_target = 0x00000000ffff0000000000000000000000000000000000000000000000000000


async def mining_subscribe(*args, **kwargs):
    if len(args) >= 1:
        kwargs['user']["miner_name"] = args[0]
    dead_beef = b'\xde\xad\xbe\xef\xca\xfe\xba\xbe'
    subscription_id_1 = dead_beef + urandom(8)
    subscription_id_2 = dead_beef + urandom(8)
    kwargs['user']["subscription_id"] = (subscription_id_1, subscription_id_2)
    subscription_details = [
        ('mining.set_difficulty', str(kwargs['user']['diff'])),
        ('mining.notify', hexlify(subscription_id_2).decode())]
    extra_nonce1 = urandom(4)
    extra_nonce2_size = 4
    kwargs['user']['extra_nonce1'] = extra_nonce1
    return subscription_details, hexlify(extra_nonce1).decode(), extra_nonce2_size


async def mining_extranonce_subscribe(*args, **kwargs):
    kwargs['user']['mining.set_extranonce'] = True
    return True


async def mining_authorize(user_name, password, **kwargs):
    kwargs['user']["user"] = user_name
    kwargs['user']["password"] = password
    return True


async def mining_submit(*args, **kwargs):
    # "slush.miner1", "bf", "00000001", "504e86ed", "b2957c02
    user_name, job_id, extra_nonce2, ntime, nonce = args
    self = kwargs['self']
    # find user
    for user in self.users.values():
        if user.user == user_name:
            break
    else:
        return 'Not found user "{}"'.format(user_name)
    # Get job info
    job_queue = kwargs['job_queue']
    mined_block = job_queue.get(int(job_id, 16))
    if mined_block is None:
        return 'Not found job {}'.format(job_id)
    mined_block.time = int.from_bytes(unhexlify(ntime.encode()), 'little')
    mined_block.nonce = unhexlify(nonce.encode())
    # reset proof tx
    proof_tx = mined_block.txs[0]
    proof_tx.b = proof_tx[:91] + user['extra_nonce1'] + unhexlify(extra_nonce2.encode()) + b''
    proof_tx.deserialize()
    mined_block.update_merkleroot()
    mined_block.update_pow()
    int.from_bytes(mined_block.work_hash, 'little')
    if base_target // user['diff'] > int.from_bytes(mined_block.work_hash, 'little'):
        return 'not satisfied request work.'
    log.info("Accept work by \"{}\"".format(user['user']))
    user['deque'].append(time())  # accept!
    if mined_block.pow_check():
        confirmed_generating_block(mined_block)
    return True


async def mining_suggest_difficulty(new_diff, **kwargs):
    kwargs['user']['diff'] = new_diff
    return True


async def mining_notify(job_id, clean_jobs, mining_block):
    job_id = hex(job_id)[2:]  # 3a40
    previous_hash = bin2hex(mining_block.previous_hash)
    # coinbase = coinbase1 + extra_nonce1 + extra_nonce2 + coinbase2
    proof_tx = mining_block.txs[0]
    proof_tx.message_type = C.MSG_BYTE
    proof_tx.message = b'\x00' * 8  # no_message tx is 91bytes, need extra
    proof_tx.serialize()
    coinbase1 = hexlify(proof_tx.b[:91]).decode()
    coinbase2 = ""
    merkleroot_branch = [bin2hex(tx.hash) for tx in mining_block.txs[1:]]  # ['ac9c224e5a1344bb659a8716c9ef5e9c7a07c71ec955260fa83964175f3014b4']
    block_version = hexlify(mining_block.version.to_bytes(4, 'little')).decode()  # 20000000
    bits = hexlify(mining_block.bits.to_bytes(4, 'big')).decode()  # 1c034394
    ntime = hexlify(mining_block.time.to_bytes(4, 'little')).decode()  # 5bd3a90a
    # clean_jobs = None  # True
    return job_id, previous_hash, coinbase1, coinbase2, \
        merkleroot_branch, block_version, bits, ntime, clean_jobs
    # work...
    # return "1378e","71de8c033056bacbe72d3032a00ab57d7c97e00c949768ea71b1bea2aaffe39d","02000000d46fd85b010000000000000000000000000000000000000000000000000000000000000000ffffffff1803b7030c04d46fd85b08","7969696d700000000000010088526a74000000232103d6359ad2e68684fac7851b5b477a616066cab3802950df41454fe763f7f20e72ac00000000",[],"00000007","1c01fb51","5bd86fd4", True


def bin2hex(b):
    return hexlify(b[::-1]).decode()


__all__ = [
    "mining_subscribe",
    "mining_extranonce_subscribe",
    "mining_authorize",
    "mining_submit",
    "mining_notify",
]
