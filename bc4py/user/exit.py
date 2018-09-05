from bc4py.config import V


def system_exit():
    if V.MINING_OBJ:
        V.MINING_OBJ.close()
    if V.STAKING_OBJ:
        V.STAKING_OBJ.close()
    if V.PC_OBJ:
        V.PC_OBJ.close()
    if V.API_OBJ:
        V.API_OBJ.cleanup()
