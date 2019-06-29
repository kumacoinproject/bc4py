from bc4py import __version__, __chain_version__, __message__
from bc4py.config import C, V, P
from bc4py.chain.utils import GompertzCurve, DEFAULT_TARGET
from bc4py.chain.difficulty import get_bits_by_hash, get_bias_by_hash
from bc4py.database.builder import chain_builder, tx_builder
from bc4py.user.api import utils
from bc4py.user.generate import generating_threads
from time import time
import p2p_python

MAX_256_FLOAT = float(0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff)
start_time = int(time())
F_ADD_CASHE_INFO = False  # to adjust cashe size

__api_version__ = '0.0.2'


async def chain_info(request):
    try:
        best_height = chain_builder.best_block.height
        best_block = chain_builder.best_block
        old_block_height = chain_builder.best_chain[0].height - 1
        old_block_hash = chain_builder.get_block_hash(old_block_height).hex()
        data = {'best': best_block.getinfo()}
        difficulty = dict()
        for consensus, ratio in V.BLOCK_CONSENSUSES.items():
            name = C.consensus2name[consensus]
            bits, target = get_bits_by_hash(previous_hash=best_block.hash, consensus=consensus)
            target = float(target)
            block_time = round(V.BLOCK_TIME_SPAN / ratio * 100)
            diff = round(DEFAULT_TARGET / target, 8)
            bias = get_bias_by_hash(previous_hash=best_block.previous_hash, consensus=consensus)
            difficulty[name] = {
                'number': consensus,
                'bits': bits.to_bytes(4, 'big').hex(),
                'diff': round(diff, 8),
                'bias': round(bias, 8),
                'fixed_diff': round(diff / bias, 8),
                'hashrate(kh/s)': round((MAX_256_FLOAT/target) / block_time / 1000, 3)
            }
        data['mining'] = difficulty
        data['size'] = best_block.size
        data['checkpoint'] = {'height': old_block_height, 'blockhash': old_block_hash}
        data['money_supply'] = GompertzCurve.calc_total_supply(best_height)
        data['total_supply'] = GompertzCurve.k
        if F_ADD_CASHE_INFO:
            data['cashe'] = {
                'get_bits_by_hash': str(get_bits_by_hash.cache_info()),
                'get_bias_by_hash': str(get_bias_by_hash.cache_info())
            }
        return utils.json_res(data)
    except Exception:
        return utils.error_res()


async def chain_fork_info(request):
    try:
        main_chain = [block.getinfo() for block in chain_builder.best_chain]
        orphan_chain = [block.getinfo() for block in chain_builder.chain.values() if block not in chain_builder.best_chain]
        data = {
            'main': main_chain,
            'orphan': sorted(orphan_chain, key=lambda x: x['height']),
            'root': chain_builder.root_block.getinfo()
        }
        return utils.json_res(data)
    except Exception:
        return utils.error_res()


async def system_info(request):
    data = {
        'system_ver': __version__,
        'api_ver': __api_version__,
        'chain_ver': __chain_version__,
        'branch': V.BRANCH_NAME,
        'booting': P.F_NOW_BOOTING,
        'connections': len(V.P2P_OBJ.core.user),
        'unconfirmed': [txhash.hex() for txhash in tx_builder.unconfirmed.keys()],
        'access_time': int(time()),
        'start_time': start_time
    }
    return utils.json_res(data)


async def system_private_info(request):
    try:
        data = {
            'system_ver': __version__,
            'api_ver': __api_version__,
            'chain_ver': __chain_version__,
            'branch': V.BRANCH_NAME,
            'message': __message__,
            'booting': P.F_NOW_BOOTING,
            'connections': len(V.P2P_OBJ.core.user),
            'unconfirmed': [txhash.hex() for txhash in tx_builder.unconfirmed.keys()],
            'directory': V.DB_HOME_DIR,
            'generate_threads': [str(s) for s in generating_threads],
            'access_time': int(time()),
            'start_time': start_time
        }
        return utils.json_res(data)
    except Exception:
        return utils.error_res()


async def network_info(request):
    try:
        peers = list()
        data = V.P2P_OBJ.core.get_my_user_header()
        for user in V.P2P_OBJ.core.user:
            peers.append({
                'number': user.number,
                'object': repr(user),
                'host_port': "{}:{}".format(*user.get_host_port()),
                'neers': ["{}:{}".format(*conn) for conn in user.neers],
                'sock_type': user.sock_type,
                'score': user.score,
                'warn': user.warn,
                'header': user.header.getinfo()
            })
        data['peers'] = peers
        return utils.json_res(data)
    except Exception:
        return utils.error_res()


__all__ = [
    "chain_info",
    "chain_fork_info",
    "system_info",
    "system_private_info",
    "network_info",
]
