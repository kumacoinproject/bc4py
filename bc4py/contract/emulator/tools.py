from bc4py.contract.emulator.virtualmachine import *
from bc4py.database.builder import tx_builder
from bc4py.database.contract import *
from bc4py.user import Accounting
from bc4py.user.network.sendnew import *
from bc4py.user.txcreation.contract import create_conclude_tx, create_signed_tx_as_validator
from io import StringIO
from logging import getLogger

log = getLogger('bc4py')


def execute(c_address, genesis_block, start_tx, c_method, redeem_address, c_args, gas_limit, f_show_log=False):
    """ execute contract emulator """
    file = StringIO()
    is_success, result, emulate_gas, work_line = emulate(
        genesis_block=genesis_block, start_tx=start_tx, c_address=c_address,
        c_method=c_method, redeem_address=redeem_address, c_args=c_args, gas_limit=gas_limit, file=file)
    if is_success:
        log.info('Success gas={} line={} result={}'.format(emulate_gas, work_line, result))
        if f_show_log:
            log.debug("#### Start log ####")
            for data in file.getvalue().split("\n"):
                log.debug(data)
            log.debug("#### Finish log ####")
    else:
        log.error('Failed gas={} line={} result=\n{}\nlog=\n{}'.format(
            emulate_gas, work_line, result, file.getvalue()))
    file.close()
    log.debug("Close file obj {}.".format(id(file)))
    return result, emulate_gas


def broadcast(c_address, start_tx, redeem_address, emulate_gas, result, f_not_send=False):
    """ broadcast conclude tx """
    if isinstance(result, tuple) and len(result) == 2:
        returns, c_storage = result
        assert returns is None or isinstance(returns, Accounting)
        assert c_storage is None or isinstance(c_storage, dict)
        # get
        if returns is None:
            send_pairs = None
        else:
            send_pairs = list()
            for address, coins in returns:
                for coin_id, amount in coins:
                    send_pairs.append((address, coin_id, amount))
    else:
        return None
    # create conclude tx
    conclude_tx = create_conclude_tx(c_address=c_address, start_tx=start_tx, redeem_address=redeem_address,
                                     send_pairs=send_pairs, c_storage=c_storage, emulate_gas=emulate_gas)
    # send tx
    another_conclude_hash = get_conclude_hash_from_start(c_address=c_address, start_hash=start_tx.hash)
    if another_conclude_hash is not None:
        if another_conclude_hash == conclude_tx.hash:
            log.debug("Already confirmed same concludeTX.")
        else:
            log.warning("Already confirmed different concludeTX.")
        return None  # Already put confirmed or unconfirmed, don't need wait
    elif f_not_send:
        log.debug("Not broadcast, send_pairs={} c_storage={} tx={}"
                      .format(send_pairs, c_storage, conclude_tx.getinfo()))
        return None
    elif send_newtx(new_tx=conclude_tx, exc_info=False):
        log.info("Broadcast success {}".format(conclude_tx))
        return conclude_tx.hash
    else:
        log.error("Failed broadcast, send_pairs={} c_storage={} tx={}"
                      .format(send_pairs, c_storage, conclude_tx.getinfo()))
        # Check already confirmed another conclude tx
        a_conclude = calc_tx_movement(
            tx=conclude_tx, c_address=c_address, redeem_address=redeem_address, emulate_gas=emulate_gas)
        a_conclude.cleanup()
        # get another ConcludeTX again
        another_hash_again = get_conclude_hash_from_start(c_address=c_address, start_hash=start_tx.hash)
        if another_hash_again is None:
            log.warning("Maybe Contract execution expired.")
            return None
        another_tx = tx_builder.get_tx(txhash=another_hash_again)
        a_another = calc_tx_movement(tx=another_tx, c_address=c_address,
                                     redeem_address=redeem_address, emulate_gas=emulate_gas)
        a_another.cleanup()
        _c_address, _start_hash, another_storage = another_tx.encoded_message()
        log.error("Failed confirm ConcludeTX, please check params\n"
                      "   AnoAccount=>{}\n   MyAccount =>{}\n"
                      "   AnoStorage=>{}\n   MyStorage =>{}\n"
                      "   AnoTX=>{}\n   MyTX =>{}\n"
                      .format(a_another, a_conclude, another_storage, c_storage, another_tx, conclude_tx))
        return None


def calc_tx_movement(tx, c_address, redeem_address, emulate_gas):
    """ Calc tx inner movement """
    account = Accounting()
    for txhash, txindex in tx.inputs:
        input_tx = tx_builder.get_tx(txhash=txhash)
        address, coin_id, amount = input_tx.outputs[txindex]
        account[address][coin_id] -= amount
    account[redeem_address][0] += (tx.gas_amount+emulate_gas) * tx.gas_price
    account[c_address][0] -= emulate_gas * tx.gas_price
    for address, coin_id, amount in tx.outputs:
        account[address][coin_id] += amount
    return account


__all__ = [
    "execute",
    "broadcast",
]
