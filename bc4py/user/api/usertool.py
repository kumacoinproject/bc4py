from bc4py import __chain_version__
from bc4py.config import V
from bc4py.chain import msgpack
from bc4py.database.builder import builder
from bc4py.user.api import web_base
from logging import getLogger
from time import time
from aiofile import AIOFile
import os

log = getLogger('bc4py')


async def create_bootstrap(request):
    try:
        boot_path = os.path.join(V.DB_HOME_DIR, 'bootstrap-ver{}.dat'.format(__chain_version__))
        if os.path.exists(boot_path):
            log.warning("remove old bootstrap.dat file")
            os.remove(boot_path)
        if builder.root_block is None:
            Exception('root block is None?')
        s = time()
        block = None
        stop_height = builder.root_block.height
        log.info("start create bootstrap.dat data to {}".format(stop_height))
        async with AIOFile(boot_path, mode='ba') as afp:
            for height, blockhash in builder.db.read_block_hash_iter(start_height=1):
                if stop_height <= height:
                    break
                block = builder.get_block(blockhash=blockhash)
                if block is None:
                    break
                await afp.write(msgpack.dumps((block, block.work_hash, block.bias)))
                if block.height % 200 == 0:
                    log.info("create bootstrap.dat height={} {}s passed".format(block.height, round(time() - s)))
                    await afp.fsync()
            log.info("create new bootstrap.dat finished, last={} {}Minutes".format(block, (time() - s) // 60))
        return web_base.json_res({
            "height": stop_height,
            "time": int(s),
        })
    except Exception:
        return web_base.error_res()


__all__ = [
    "create_bootstrap",
]
