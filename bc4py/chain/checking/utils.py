from bc4py.config import C, V, BlockChainError
from bc4py.database.builder import builder, tx_builder
from bc4py.database.tools import get_usedindex
from bc4py.database.validator import get_validator_object
from bc4py.chain.checking.signature import get_signed_cks
from bc4py.user import Balance
from nem_ed25519 import is_address


def inputs_origin_check(tx, include_block):
    # Blockに取り込まれているなら
    # TXのInputsも既に取り込まれているはずだ
    limit_height = builder.best_block.height - C.MATURE_HEIGHT
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            # InputのOriginが存在しない
            raise BlockChainError('Not found input tx. {}:{}'.format(txhash.hex(), txindex))
        elif input_tx.height is None:
            # InputのOriginはUnconfirmed
            if include_block:
                raise BlockChainError('TX {} is include'
                                      ', but input origin {} is unconfirmed.'.format(tx, input_tx))
            else:
                # UnconfirmedTXの受け入れなので、txもinput_txもUnconfirmed
                pass  # OK
        elif input_tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD) and \
                input_tx.height > limit_height:
            raise BlockChainError('input origin is proof tx, {}>{}'.format(input_tx.height, limit_height))
        else:
            # InputのOriginは既に取り込まれている
            pass  # OK
        # 使用済みかチェック
        if txindex in get_usedindex(txhash=txhash, best_block=include_block):
            raise BlockChainError('1 Input of {} is already used! {}:{}'.format(tx, txhash.hex(), txindex))
        # 同一Block内で使用されていないかチェック
        if include_block:
            for input_tx in include_block.txs:
                if input_tx == tx:
                    break
                for input_hash, input_index in input_tx.inputs:
                    if input_hash == txhash and input_index == txindex:
                        raise BlockChainError('2 Input of {} is already used by {}'.format(tx, input_tx))


def amount_check(tx, payfee_coin_id):
    # Inputs
    input_coins = Balance()
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            raise BlockChainError('Not found input tx {}'.format(txhash.hex()))
        address, coin_id, amount = input_tx.outputs[txindex]
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
    signed_cks = get_signed_cks(tx)
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash)
        if input_tx is None:
            raise BlockChainError('Not found input tx {}'.format(txhash.hex()))
        if len(input_tx.outputs) <= txindex:
            raise BlockChainError('txindex is over range {}<={}'.format(len(input_tx.outputs), txindex))
        address, coin_id, amount = input_tx.outputs[txindex]
        if address in checked_cks:
            continue
        elif is_address(address, V.BLOCK_PREFIX):
            require_cks.add(address)
        elif is_address(address, V.BLOCK_VALIDATOR_PREFIX):
            v_before = get_validator_object(v_address=address, best_block=include_block, stop_txhash=tx.hash)
            if v_before.version == -1:
                raise BlockChainError('Not init validator {}'.format(address))
            if len(signed_cks & v_before.validators) < v_before.require:
                raise BlockChainError('Don\'t satisfy required signature {}<{}'.format(
                    len(signed_cks & v_before.validators), v_before.require))
            require_cks.update(v_before.validators)
        elif is_address(address, V.BLOCK_CONTRACT_PREFIX):
            raise BlockChainError('Not allow ContractAddress include in normal Transfer. {}'.format(address, tx))
        else:
            raise BlockChainError('Not common address {} {}.'.format(address, tx))
        # success check
        checked_cks.add(address)

    if not (0 < len(require_cks) < 256):
        raise BlockChainError('require signature is over range num={}'.format(len(require_cks)))
    if require_cks != signed_cks:
        raise BlockChainError('Signature verification failed. [{}={}]'.format(require_cks, signed_cks))


__all__ = [
    "inputs_origin_check",
    "amount_check",
    "signature_check",
]
