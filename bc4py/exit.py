from bc4py.config import V, P
from logging import getLogger
import asyncio


log = getLogger('bc4py')
loop = asyncio.get_event_loop()


async def system_safe_exit():
    """system safe exit method"""
    log.info("start system stop process")
    try:
        P.F_STOP = True
        from bc4py.database.builder import chain_builder
        chain_builder.close()

        if V.API_OBJ:
            await V.API_OBJ.shutdown()  # should be called before cleanup()
            await V.API_OBJ.cleanup()  # should be called after shutdown()

        if V.P2P_OBJ:
            V.P2P_OBJ.close()

        loop.stop()
    except Exception:
        log.warning("failed system stop process", exc_info=True)
    else:
        log.info("success system stop process")


__all__ = [
    "system_safe_exit",
]
