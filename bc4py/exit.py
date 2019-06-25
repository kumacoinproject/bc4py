from bc4py.config import V, P, stream
from logging import getLogger
import asyncio


log = getLogger('bc4py')
loop = asyncio.get_event_loop()


async def system_safe_exit():
    """system safe exit method"""
    log.info("start system stop process")
    try:
        P.F_STOP = True

        # reactive stream close
        stream.dispose()

        from bc4py.database.builder import chain_builder
        await chain_builder.close()

        if V.API_OBJ:
            await V.API_OBJ.shutdown()  # should be called before cleanup()
            await V.API_OBJ.cleanup()  # should be called after shutdown()

        if V.P2P_OBJ:
            V.P2P_OBJ.close()

        log.info("wait all tasks for max 15s..")
        await asyncio.wait(asyncio.Task.all_tasks(), timeout=15.0)
        log.info("stop waiting tasks and close after 1s")
        loop.call_later(1.0, loop.stop)
    except Exception:
        log.warning("failed system stop process", exc_info=True)
    else:
        log.info("success system stop process")


__all__ = [
    "system_safe_exit",
]
