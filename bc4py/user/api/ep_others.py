from bc4py import __chain_version__
from bc4py.config import V
from bc4py.chain import msgpack
from bc4py.database.builder import chain_builder
from bc4py.user.api.utils import auth, error_response
from fastapi import Depends
from fastapi.security import HTTPBasicCredentials
from logging import getLogger
from time import time
import asyncio
import gzip
import os

loop = asyncio.get_event_loop()
log = getLogger('bc4py')


async def create_bootstrap(credentials: HTTPBasicCredentials = Depends(auth)):
    """
    This end-point create bootstrap.tar.gz file.
    * About
        * It will take some minutes.
    """
    try:
        boot_path = os.path.join(V.DB_HOME_DIR, 'bootstrap-ver{}.dat.gz'.format(__chain_version__))
        if os.path.exists(boot_path):
            log.warning("remove old bootstrap.dat.gz file")
            os.remove(boot_path)
        if chain_builder.root_block is None:
            Exception('root block is None?')

        s = time()
        block = None
        size = 0.0  # MB
        stop_height = chain_builder.root_block.height
        log.info("start create bootstrap.dat.gz data to {}".format(stop_height))
        with gzip.open(boot_path, mode='wb') as fp:
            for height, blockhash in chain_builder.db.read_block_hash_iter(start_height=1):
                if stop_height <= height:
                    break
                block = chain_builder.get_block(blockhash=blockhash)
                if block is None:
                    break
                await loop.run_in_executor(
                    None, fp.write, msgpack.dumps((block, block.work_hash, block.bias)))
                size += block.total_size / 1000000
                if block.height % 300 == 0:
                    log.info("create bootstrap.dat.gz height={} size={}mb {}s passed"
                             .format(block.height, round(size, 2), round(time() - s)))

        log.info("create new bootstrap.dat.gz finished, last={} size={}gb time={}m"
                 .format(block, round(size/1000, 3), (time() - s) // 60))
        return {
            "height": stop_height,
            "total_size": size,
            "start_time": int(s),
            "finish_time": int(time()),
        }
    except Exception:
        return error_response()


__all__ = [
    "create_bootstrap",
]
