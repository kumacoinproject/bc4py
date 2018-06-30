from bc4py.contract.libs import *


"""
address => UUID でIDを定義
CMD+UUID => Paramsでパラメーターを定義

 :cmd   :param           :value
b'\x00' is_validator     0=no, 1=yes
b'\x01' balance          int unsigned
b'\x02' quit_validator   quit request height
b'\x03' validator_key    publicKey + msg
b'\x04' accept_index     int unsigned, msg+index signature check
c_data
cmd, dataのtuple
 :cmd        :data
deposit      address
withdraw     (address, message, signature, amount)
lock         (address, message, signature)
unlock       (address, message, signature)
"""

# TODO: 設計


class Contract:
    def __init__(self, start_tx, c_address):
        self.start_tx = start_tx
        self.c_address = c_address
