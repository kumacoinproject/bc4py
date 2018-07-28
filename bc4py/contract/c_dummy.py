from bc4py.contract.libs import *


class Contract:
    def __init__(self, start_tx, c_address):
        self.start_tx = start_tx
        self.c_address = c_address
