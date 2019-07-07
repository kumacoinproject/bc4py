from bc4py import __chain_version__
from bc4py.config import C, V
from bc4py.database.builder import chain_builder, tx_builder
from bc4py.user.generate import create_mining_block, confirmed_generating_block, FailedGenerateWarning
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from binascii import a2b_hex
from time import time
from expiringdict import ExpiringDict
import asyncio
from logging import getLogger


log = getLogger('bc4py')

getwork_cashe = ExpiringDict(max_len=100, max_age_seconds=300)
extra_target = None  # 0x00000000ffff0000000000000000000000000000000000000000000000000000


async def get_mining_block(consensus):
    """create raw mining block"""
    s = time()
    while True:
        try:
            return await create_mining_block(consensus=consensus)
        except FailedGenerateWarning:
            await asyncio.sleep(0.1)
        except Exception as e:
            if time() - s > 5:
                raise TimeoutError("Mining block creation failed by '{}'".format(e))
            await asyncio.sleep(0.1)


async def getwork(*args, **kwargs):
    """
    https://en.bitcoin.it/wiki/Getwork
    Result:
        1. "data"       (hex string, required) block data
        2. "target"     (hex string, required) little endian hash target
    """
    if len(args) == 0:
        now = int(time() - V.BLOCK_GENESIS_TIME)
        for block in getwork_cashe.values():
            if block.previous_hash != chain_builder.best_block.hash:
                continue
            if now - block.time < 10:
                mining_block = block
                break
        else:
            mining_block = await get_mining_block(int(kwargs['password']))
            getwork_cashe[mining_block.merkleroot] = mining_block
            mining_block.bits2target()
        # Pre-processed SHA-2 input chunks
        data = mining_block.b  # 80 bytes
        data += a2b_hex('800000000000000000000000000000000000000000000000'
                        '000000000000000000000000000000000000000000000280')  # 48+80=128bytes
        new_data = b''
        for i in range(0, 128, 4):
            new_data += data[i:i + 4][::-1]
        if extra_target:
            return {"data": new_data.hex(), "target": extra_target.to_bytes(32, 'big').hex()}
        else:
            return {"data": new_data.hex(), "target": mining_block.target_hash.hex()}
    else:
        data = a2b_hex(args[0])
        new_data = b''
        for i in range(0, 128, 4):
            new_data += data[i:i + 4][::-1]
        block = Block.from_binary(binary=new_data[:80])
        if block.previous_hash != chain_builder.best_block.hash:
            return 'PreviousHash don\'t match'
        if block.merkleroot in getwork_cashe:
            block.txs.extend(getwork_cashe[block.merkleroot].txs)
            result = await submitblock(block, **kwargs)
            if result is None:
                return True
            elif extra_target and block.pow_check(extra_target=extra_target):
                return True
            else:
                log.debug("GetWorkReject by \"{}\"".format(result))
                return result
        else:
            log.debug("GetWorkReject by \"Not found merkleroot.\"")
            return 'Not found merkleroot'


async def getblocktemplate(*args, **kwargs):
    """
    https://en.bitcoin.it/wiki/Getblocktemplate
    For full specification, see BIPs 22, 23, 9, and 145:
        https://github.com/bitcoin/bips/blob/master/bip-0022.mediawiki
        https://github.com/bitcoin/bips/blob/master/bip-0023.mediawiki
        https://github.com/bitcoin/bips/blob/master/bip-0009.mediawiki#getblocktemplate_changes
        https://github.com/bitcoin/bips/blob/master/bip-0145.mediawiki

    Arguments:
    1. template_request         (json object, optional) A json object in the following spec
         {
           "mode":"template"    (string, optional) This must be set to "template", "proposal" (see BIP 23), or omitted
           "capabilities":[     (array, optional) A list of strings
               "support"          (string) client side supported feature, 'longpoll', 'coinbasetxn', 'coinbasevalue', 'proposal', 'serverlist', 'workid'
               ,...
           ],
           "rules":[            (array, optional) A list of strings
               "support"          (string) client side supported softfork deployment
               ,...
           ]
         }

    Result:
    {
      "version" : n,                    (numeric) The preferred block version
      "previousblockhash" : "xxxx",     (string) The hash of current highest block
      "transactions" : [                (array) contents of non-coinbase transactions that should be included in the next block
        {
          "data" : "xxxx",             (string) transaction data encoded in hexadecimal (byte-for-byte)
           "txid" : "xxxx",             (string) transaction id encoded in little-endian hexadecimal
           "hash" : "xxxx",             (string) hash encoded in little-endian hexadecimal (including witness data)
           "depends" : [                (array) array of numbers
              n                          (numeric) transactions before this one (by 1-based index in 'transactions' list) that must be present in the final block if this one is
              ,...
           ],
           "fee": n,                    (numeric) difference in value between transaction inputs and outputs (in satoshis); for coinbase transactions, this is a negative Number of the total collected block fees (ie, not including the block subsidy); if key is not present, fee is unknown and clients MUST NOT assume there isn't one
           "sigops" : n,                (numeric) total SigOps cost, as counted for purposes of block limits; if key is not present, sigop cost is unknown and clients MUST NOT assume it is zero
           "weight" : n,                (numeric) total transaction weight, as counted for purposes of block limits
           "required" : true|false      (boolean) if provided and true, this transaction must be in the final block
        }
        ,...
      ],
      "target" : "xxxx",                (string) The hash target
      "curtime" : ttt,                  (numeric) current timestamp in seconds since epoch (Jan 1 1970 GMT)
      "mutable" : [                     (array of string) list of ways the block template may be changed
         "value"                          (string) A way the block template may be changed, e.g. 'time', 'transactions', 'prevblock'
         ,...
      ],
      "noncerange" : "00000000ffffffff",(string) A range of valid nonces
      "sizelimit" : n,                  (numeric) limit of block size
      "bits" : "xxxxxxxx",              (string) compressed target of next block
      "height" : n                      (numeric) The height of the next block
    }
    See https://en.bitcoin.it/wiki/BIP_0022 for full specification.
    """
    # check option
    template_request = args[0] if 0 < len(args) else dict()
    if isinstance(template_request, dict) and 'capabilities' in template_request:
        # "coinbasetxn", "workid", "coinbase/append", "messagenonce"
        capabilities = template_request['capabilities']
    else:
        capabilities = ['coinbasetxn']
    # generate block
    mining_block = await get_mining_block(int(kwargs['password']))
    mining_block.bits2target()
    # add capability "messagenonce"
    if 'messagenonce' in capabilities:
        coinbase: TX = mining_block.txs[0]
        # ffffffff  0c    03      9e1b00  00000000     00000000
        # prefix    push  length  height  extranonce1  extranoce2
        # [dummy 6bytes]-[height 3bytes]-[extranonce1 4bytes]-[extranonce2 4bytes]
        coinbase.message = a2b_hex('ffffffff0c03') + mining_block.height.to_bytes(3, 'little') + b'\x00' * 8
        coinbase.message_type = C.MSG_BYTE
        coinbase.serialize()
    # generate template
    template = {
        "version": mining_block.version,
        "previousblockhash": reversed_hex(mining_block.previous_hash),
        "transactions": None,
        "coinbasetxn": {
            # sgminer say, FAILED to decipher work from 127.0.0.1
            "data": mining_block.txs[0].b.hex()
        },  # 採掘報酬TX
        "target": reversed_hex(mining_block.target_hash),
        "mutable": ["time", "transactions", "prevblock"],
        "noncerange": "00000000ffffffff",
        "sizelimit": C.SIZE_BLOCK_LIMIT,
        "curtime": mining_block.time,  # block time
        "bits": mining_block.bits.to_bytes(4, 'big').hex(),
        "time": mining_block.time,
        "height": mining_block.height
    }
    transactions = list()
    for tx in mining_block.txs[1:]:
        transactions.append({
            "data": tx.b.hex(),
            "hash": reversed_hex(tx.hash),
            "depends": list(),
            "fee": tx.gas_price * tx.gas_amount,
        })
    template['transactions'] = transactions
    return template


async def submitblock(*args, **kwargs):
    """
    Attempts to submit new block to network.
    See https://en.bitcoin.it/wiki/BIP_0022 for full specification.

    Arguments
        1. "hexdata"        (string, required) the hex-encoded block data to submit
        2. "dummy"          (optional) dummy value, for compatibility with BIP22. This value is ignored.

    Result:
        null if success
        string if failed
    """
    if len(args) == 0:
        raise ValueError('no argument found')
    block_hex_or_obj = args[0]
    if isinstance(block_hex_or_obj, str):
        block_bin = a2b_hex(block_hex_or_obj)
        # Block
        mined_block = Block.from_binary(binary=block_bin[:80])
        if mined_block.previous_hash != chain_builder.best_block.hash:
            return 'PreviousHash don\'t match'
        previous_block = chain_builder.get_block(mined_block.previous_hash)
        mined_block.height = previous_block.height + 1
        mined_block.flag = int(kwargs['password'])
        # tx length
        storage_flag = int.from_bytes(block_bin[80:81], 'little')
        if storage_flag < 0xfd:
            tx_len = storage_flag
            pos = 81
        elif storage_flag == 0xfd:
            tx_len = int.from_bytes(block_bin[81:83], 'little')
            pos = 83
        elif storage_flag == 0xfe:
            tx_len = int.from_bytes(block_bin[81:85], 'little')
            pos = 85
        else:  # == 0xff
            tx_len = int.from_bytes(block_bin[81:89], 'little')
            pos = 89
        log.debug("RpcSubmit block: pos={}, tx_len={}".format(pos, tx_len))
        # correct txs
        while len(block_bin) > pos:
            tx = TX()
            tx.b = block_bin
            tx.deserialize(first_pos=pos, f_raise=False)
            if tx.version != __chain_version__:
                return 'tx_ver do not match [{}!={}]'.format(tx.version, __chain_version__)
            pos += len(tx.b)
            mined_block.txs.append(tx_builder.get_tx(txhash=tx.hash, default=tx))
        # check format
        if tx_len != len(mined_block.txs):
            return 'Do not match txlen [{}!={}]'.format(tx_len, len(mined_block.txs))
        if pos != len(block_bin):
            return 'Do not match pos [{}!={}]'.format(pos, len(block_bin))
    elif isinstance(block_hex_or_obj, Block):
        mined_block = block_hex_or_obj
        previous_block = chain_builder.get_block(mined_block.previous_hash)
        mined_block.height = previous_block.height + 1
        mined_block.flag = int(kwargs['password'])
    else:
        return 'Unknown input? -> {}'.format(block_hex_or_obj)
    mined_block.update_pow()
    if mined_block.pow_check():
        await confirmed_generating_block(mined_block)
        return None  # accepted
    else:
        return 'not satisfied work'


def reversed_hex(b):
    return b[::-1].hex()


__all__ = [
    "getwork",
    "getblocktemplate",
    "submitblock",
]
