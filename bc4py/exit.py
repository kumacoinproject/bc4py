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

        from bc4py.user.generate import close_generate
        close_generate()

        if V.API_OBJ:
            V.API_OBJ.handle_exit(None, None)
            await V.API_OBJ.shutdown()

        if V.P2P_OBJ:
            V.P2P_OBJ.close()

        log.info("wait all tasks for max 15s..")
        all_task = asyncio.Task.all_tasks()
        all_task.remove(asyncio.Task.current_task())
        await asyncio.wait(all_task, timeout=15.0)
        log.info("stop waiting tasks and close after 1s")
        loop.call_later(1.0, loop.stop)
    except Exception:
        log.warning("failed system stop process", exc_info=True)
    else:
        log.info("success system stop process")


def blocking_run():
    """block and exit with system_safe_exit"""
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("stop blocking run!")
        loop.run_until_complete(system_safe_exit())
    loop.close()


__all__ = [
    "system_safe_exit",
    "blocking_run",
]
