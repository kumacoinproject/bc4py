from bc4py.config import V, P
import asyncio


def system_exit():
    pass
    # Disabled
    #if V.MINING_OBJ:
    #    V.MINING_OBJ.close()
    #if V.STAKING_OBJ:
    #    V.STAKING_OBJ.close()
    #if V.PC_OBJ:
    #    V.PC_OBJ.close()
    #if V.API_OBJ:
    #    asyncio.get_event_loop().close()
    # asyncio.get_event_loop().run_until_complete(api_close())


async def api_close():
    await V.API_OBJ.shutdown()
    await V.API_OBJ.cleanup()
