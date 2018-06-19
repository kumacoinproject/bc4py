from bc4py.contract.libs import *

"""
c_cs
Key = [cmd 1byte]-[address 40bytes]
Value = [something Nbytes]
Keyの中身
 :cmd   :param         :len  :value
b'\x00' is_validator   1     0=no, 1=yes
b'\x01' balance        8     int unsigned
b'\x02' quit_validator 4     quit request height
b'\x03' validator_key  64    publicKey + msg
b'\x04' accept_index   4     int unsigned, msg+index signature check

c_data
cmd, dataのtuple
 :cmd        :data
deposit      address
withdraw     (address, message, signature, amount)
lock         (address, message, signature)
unlock       (address, message, signature)
"""

# TODO: 仕組み構築


def contract(c_address, c_tx):
    c_cs = get_storage_by_address(c_address)
    c_data = get_tx_message_data(c_tx)
    outputs = list()
    return outputs, c_cs
