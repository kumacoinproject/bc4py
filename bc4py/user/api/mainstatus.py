from bc4py import __version__, __chain_version__
from bc4py.config import C, V, P
from bc4py.chain.utils import GompertzCurve
from bc4py.chain.difficulty import get_bits_by_hash, get_pos_bias_by_hash
from bc4py.database.create import closing, create_db
from bc4py.database.chain.read import max_block_height, read_best_block, fill_tx_objects, cashe_info
from bc4py.database.user.flag import is_locked_database
from bc4py.user.api import web_base
from binascii import hexlify
import time

MAX_256_INT = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
start_time = int(time.time())

__api_version__ = '0.0.1'


def api_version():
    with open('./__init__.py', mode='r') as fp:
        for line in fp.readline():
            if line.startswith('__api_version__'):
                line.split('=')[1].strip().replace("'", '')


async def get_chain_info(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        best_height = max_block_height(cur=cur)
        best_block = read_best_block(height=best_height, cur=cur)
        best_block.f_orphan = False
        fill_tx_objects(block=best_block, cur=cur)
        data = best_block.getinfo()
        pos_bias = get_pos_bias_by_hash(previous_hash=best_block.previous_hash)[1]
        pos_target = get_bits_by_hash(previous_hash=best_block.previous_hash, consensus=C.BLOCK_POS)[1]
        pow_target = get_bits_by_hash(previous_hash=best_block.previous_hash, consensus=C.BLOCK_POW)[1]
        data['difficulty'] = {
            'pos': round(MAX_256_INT / pos_target / 100000000, 6),
            'pow': round(MAX_256_INT / pow_target / 100000000, 6),
            'bias': pos_bias,
            'hashrate(Mh/s)': round(MAX_256_INT/pow_target/V.BLOCK_TIME_SPAN/1000000, 3)}
        data['size'] = best_block.getsize()
        checkpoint_height, checkpoint_hash = max(P.CHECK_POINTS), P.CHECK_POINTS[max(P.CHECK_POINTS)]
        data['checkpoint'] = {'height': checkpoint_height, 'blockhash': hexlify(checkpoint_hash).decode()}
        data['money_supply'] = GompertzCurve.calc_total_supply(best_height)
        data['total_supply'] = GompertzCurve.k
    return web_base.json_res(data)


async def get_system_info(request):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        data = {
            'system_ver': __version__,
            'api_ver': __api_version__,
            'chain_ver': __chain_version__,
            'booting': P.F_NOW_BOOTING,
            'connections': len(V.PC_OBJ.p2p.user),
            'unconfirmed': [hexlify(txhash).decode() for txhash in P.UNCONFIRMED_TX],
            'directory': V.DB_HOME_DIR,
            'encryption': '*'*len(V.ENCRYPT_KEY) if V.ENCRYPT_KEY else V.ENCRYPT_KEY,
            'mining': {
                'address': V.MINING_ADDRESS,
                'message': V.MINING_MESSAGE,
                'status': bool(V.MINING_OBJ),
                'threads': V.MINING_OBJ.getinfo() if V.MINING_OBJ else None},
            'staking': {
                'status': bool(V.STAKING_OBJ),
                'threads': V.STAKING_OBJ.getinfo() if V.STAKING_OBJ else None},
            'locked': is_locked_database(cur),
            'debug': V.F_DEBUG,
            'cashe_size(Block, TX)': cashe_info(),
            'access_time': int(time.time()),
            'start_time': start_time}
    return web_base.json_res(data)


__all__ = [
    "get_chain_info", "get_system_info"
]
