from bc4py import __version__, __chain_version__, __message__
from bc4py.config import C, V, P
from bc4py.chain.utils import GompertzCurve
from bc4py.chain.difficulty import get_bits_by_hash, get_bias_by_hash
from bc4py.database.create import closing, create_db
from bc4py.database.builder import builder, tx_builder
from bc4py.database.keylock import is_locked_database
from bc4py.database.tools import get_validator_info
from bc4py.user.utils import im_a_validator
from bc4py.user.api import web_base
from bc4py.user.generate import generating_threads
from binascii import hexlify
import time
import p2p_python


MAX_256_INT = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
start_time = int(time.time())

__api_version__ = '0.0.1'


async def chain_info(request):
    best_height = builder.best_block.height
    best_block = builder.best_block
    old_block_height = builder.best_chain[0].height - 1
    old_block_hash = hexlify(builder.get_block_hash(old_block_height)).decode()
    data = {'best': best_block.getinfo()}
    difficulty = dict()
    for consensus, ratio in V.BLOCK_CONSENSUS.items():
        name = C.consensus2name[consensus]
        target = get_bits_by_hash(previous_hash=best_block.hash, consensus=consensus)[1]
        block_time = round(V.BLOCK_TIME_SPAN / ratio * 100)
        difficulty[name] = {
            'diff': round((MAX_256_INT // target) / 100000000, 6),
            'bias': get_bias_by_hash(previous_hash=best_block.previous_hash, consensus=consensus),
            'hashrate(kh/s)': round((MAX_256_INT//target)/block_time/1000, 3)
        }
    data['mining'] = difficulty
    data['size'] = best_block.getsize()
    data['checkpoint'] = {'height': old_block_height, 'blockhash': old_block_hash}
    data['money_supply'] = GompertzCurve.calc_total_supply(best_height)
    data['total_supply'] = GompertzCurve.k
    return web_base.json_res(data)


async def system_info(request):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        data = {
            'system_ver': __version__,
            'api_ver': __api_version__,
            'chain_ver': __chain_version__,
            'message': __message__,
            'booting': P.F_NOW_BOOTING,
            'connections': len(V.PC_OBJ.p2p.user),
            'unconfirmed': [hexlify(txhash).decode() for txhash in tx_builder.unconfirmed.keys()],
            'directory': V.DB_HOME_DIR,
            'encryption': '*'*len(V.ENCRYPT_KEY) if V.ENCRYPT_KEY else V.ENCRYPT_KEY,
            'generate': {
                'address': V.MINING_ADDRESS,
                'message': V.MINING_MESSAGE,
                'threads': [str(s) for s in generating_threads]
            },
            'locked': is_locked_database(cur),
            'access_time': int(time.time()),
            'start_time': start_time}
    return web_base.json_res(data)


async def network_info(request):
    try:
        data = {
            'p2p_ver': p2p_python.__version__,
            'status': V.PC_OBJ.p2p.get_server_header(),
            'networks': list()}
        for user in V.PC_OBJ.p2p.user:
            info = user.getinfo()
            del info['aeskey'], info['sock']
            info['neers'] = ["{}:{}".format(*conn) for conn in info['neers']]
            info['host_port'] = "{}:{}".format(*info['host_port'])
            data['networks'].append(info)
        return web_base.json_res(data)
    except BaseException:
        return web_base.error_res()


async def validator_info(request):
    try:
        validator_cks, required_num = get_validator_info()
        return web_base.json_res({
            'im_a_validator': im_a_validator(),
            'validator_address': V.CONTRACT_VALIDATOR_ADDRESS,
            'validators': list(validator_cks),
            'all': len(validator_cks),
            'require': required_num})
    except BaseException:
        return web_base.error_res()


__all__ = [
    "chain_info", "system_info", "network_info", "validator_info"
]
