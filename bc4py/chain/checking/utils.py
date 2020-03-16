from bc4py.config import C, V, BlockChainError
from bc4py.bip32 import is_address
from bc4py.database import obj
from bc4py.database.tools import is_unused_index, get_output_from_input
from bc4py.user import Balance
from hashlib import sha256


def inputs_origin_check(tx, include_block):
    """check the TX inputs for inconsistencies"""
    # check if the same input is used in same tx
    if len(tx.inputs) != len(set(tx.inputs)):
        raise BlockChainError(f"input has same origin {len(tx.inputs)}!={len(set(tx.inputs))}")

    limit_height = obj.chain_builder.best_block.height - C.MATURE_HEIGHT
    for txhash, txindex in tx.inputs:
        pair = get_output_from_input(input_hash=txhash, input_index=txindex, best_block=include_block)
        if pair is None:
            raise BlockChainError('Not found input tx. {}:{}'.format(txhash.hex(), txindex))

        if txhash in obj.tx_builder.unconfirmed:
            # input of tx is not unconfirmed because the tx is already included in Block
            if include_block is not None:
                raise BlockChainError('TX is include but input is unconfirmed {} {}'.format(tx, txhash.hex()))

        # mined output is must mature the height
        if not is_mature_input(base_hash=txhash, limit_height=limit_height):
            check_tx = obj.tx_builder.get_memorized_tx(txhash)
            if check_tx is None:
                raise Exception('cannot get tx, memory block number is too few')
            if check_tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
                raise BlockChainError('input origin is proof tx, {}>{}'.format(check_tx.height, limit_height))

        # check unused input
        if not is_unused_index(input_hash=txhash, input_index=txindex, best_block=include_block):
            raise BlockChainError('1 Input of {} is already used! {}:{}'.format(tx, txhash.hex(), txindex))

        # check if the same input is used by another tx in block
        if include_block:
            for input_tx in include_block.txs:
                if input_tx is tx:
                    continue
                for input_hash, input_index in input_tx.inputs:
                    if input_hash == txhash and input_index == txindex:
                        raise BlockChainError('2 Input of {} is already used by {}'.format(tx, input_tx))


def amount_check(tx, payfee_coin_id, include_block):
    """check tx sum of inputs and outputs amount"""
    # Inputs
    input_coins = Balance()
    for txhash, txindex in tx.inputs:
        pair = get_output_from_input(input_hash=txhash, input_index=txindex, best_block=include_block)
        if pair is None:
            raise BlockChainError('Not found input tx {}'.format(txhash.hex()))
        address, coin_id, amount = pair
        input_coins[coin_id] += amount

    # Outputs
    output_coins = Balance()
    for address, coin_id, amount in tx.outputs:
        if amount <= 0:
            raise BlockChainError('Input amount is more than 0')
        output_coins[coin_id] += amount

    # Fee
    fee_coins = Balance(coin_id=payfee_coin_id, amount=tx.gas_price * tx.gas_amount)

    # Check all plus amount
    remain_amount = input_coins - output_coins - fee_coins
    if not remain_amount.is_empty():
        raise BlockChainError('77 Don\'t match input/output. {}={}-{}-{}'.format(
            remain_amount, input_coins, output_coins, fee_coins))


def signature_check(tx, include_block):
    require_cks = set()
    checked_cks = set()
    signed_cks = set(tx.verified_list)
    for txhash, txindex in tx.inputs:
        pair = get_output_from_input(txhash, txindex, best_block=include_block)
        if pair is None:
            raise BlockChainError('Not found input tx {}'.format(txhash.hex()))
        address, coin_id, amount = pair
        if address in checked_cks:
            continue
        elif is_address(ck=address, hrp=V.BECH32_HRP, ver=C.ADDR_NORMAL_VER):
            require_cks.add(address)
        else:
            raise BlockChainError('Not common address {} {}'.format(address, tx))
        # success check
        checked_cks.add(address)

    if not (0 < len(require_cks) < 256):
        raise BlockChainError('require signature is over range num={}'.format(len(require_cks)))
    if require_cks != signed_cks:
        raise BlockChainError('Signature verification failed. [{}={}]'.format(require_cks, signed_cks))


def stake_coin_check(tx, previous_hash, target_hash):
    # staked => sha256(txhash + previous_hash) / amount < 256^32 / target
    assert tx.pos_amount is not None
    pos_work_hash = sha256(tx.hash + previous_hash).digest()
    work = int.from_bytes(pos_work_hash, 'little')
    work //= (tx.pos_amount // 100000000)
    return work < int.from_bytes(target_hash, 'little')


def is_mature_input(base_hash, limit_height) -> bool:
    """proof of stake input must mature same height"""
    # from unconfirmed
    for tx in obj.tx_builder.unconfirmed.values():
        if tx.hash == base_hash:
            return False

    # from memory
    for block in obj.chain_builder.best_chain:
        if block.height < limit_height:
            return True
        for tx in block.txs:
            if tx.hash == base_hash:
                return False

    # from database
    height = obj.chain_builder.root_block.height
    while limit_height <= height:
        block = obj.chain_builder.get_block(height=height)
        for tx in block.txs:
            if tx.hash == base_hash:
                return False
        height -= 1

    # check passed
    return True


__all__ = [
    "inputs_origin_check",
    "amount_check",
    "signature_check",
    "stake_coin_check",
    "is_mature_input",
]
