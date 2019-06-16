from bc4py import __chain_version__
from bc4py.config import V
from bc4py.chain import msgpack
from bc4py.database.builder import chain_builder
from bc4py.user.api import utils
from logging import getLogger
from time import time
import asyncio
import gzip
import os

log = getLogger('bc4py')


async def create_bootstrap(request):
    try:
        boot_path = os.path.join(V.DB_HOME_DIR, 'bootstrap-ver{}.dat.gz'.format(__chain_version__))
        if os.path.exists(boot_path):
            log.warning("remove old bootstrap.dat.gz file")
            os.remove(boot_path)
        if chain_builder.root_block is None:
            Exception('root block is None?')
        s = time()
        block = None
        stop_height = chain_builder.root_block.height
        log.info("start create bootstrap.dat.gz data to {}".format(stop_height))
        with gzip.open(boot_path, mode='ab') as fp:
            for height, blockhash in chain_builder.db.read_block_hash_iter(start_height=1):
                if stop_height <= height:
                    break
                block = chain_builder.get_block(blockhash=blockhash)
                if block is None:
                    break
                fp.write(msgpack.dumps((block, block.work_hash, block.bias)))
                await asyncio.sleep(0.0)
                if block.height % 100 == 0:
                    log.info("create bootstrap.dat.gz height={} {}s passed".format(block.height, round(time() - s)))
        log.info("create new bootstrap.dat.gz finished, last={} {}Minutes".format(block, (time() - s) // 60))
        return utils.json_res({
            "height": stop_height,
            "start_time": int(s),
            "finish_time": int(time())
        })
    except Exception:
        return utils.error_res()


__all__ = [
    "create_bootstrap",
]
