from bc4py import __chain_version__
from bc4py.config import C, V
from bc4py.chain import TX
from bc4py.contract.finishtx import check_output_format, create_finish_tx
from bc4py.database.chain.read import max_block_height
from bc4py.database.user.write import new_contract_keypair
from bc4py.user.utxo import get_unspent, full_unspents
from bc4py.user.txcreation.utils import *
import time
import bjson


def create_contract_tx(contract, chain_cur, account_cur,
                       from_group=C.ANT_UNKNOWN, gas_price=None, retention=10800):
    gas_price = gas_price if gas_price else V.COIN_MINIMUM_PRICE
    assert gas_price >= V.COIN_MINIMUM_PRICE, 'Too low gas price {}>={}'.format(gas_price, V.COIN_MINIMUM_PRICE)
    assert isinstance(contract, bytes), 'contract is bytes code.'
    # TXを作成
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    c_address = new_contract_keypair(account_cur)
    message = bjson.dumps((c_address, contract))
    tx = TX(tx={
        'version': __chain_version__,
        'type': C.TX_CREATE_CONTRACT,
        'time': now,
        'deadline': now + retention,
        'inputs': list(),
        'outputs': list(),
        'gas_price': gas_price,
        'gas_amount': 1,
        'message_type': C.MSG_BYTE,
        'message': message})
    tx.gas_amount = tx.getsize() + C.CONTRACT_CREATE_FEE + 96
    # 全てのUnspentを取得
    unspent_pairs, orphan_pairs = get_unspent(chain_cur=chain_cur, account_cur=account_cur)
    unspents = full_unspents(unspent_pairs, chain_cur)
    # input/outputを補充
    input_address = fill_inputs_outputs(tx, unspents, chain_cur, additional_fee=C.CONTRACT_CREATE_FEE)
    # RedeemDummyAddressを入れ替え
    new_redeem_address = replace_redeem_dummy_address(tx, account_cur)
    # Account間の移動をログに記録
    tx.serialize()
    recode_account_movement(tx, new_redeem_address, from_group, chain_cur, account_cur)
    # 署名をする
    setup_signature(tx, input_address)
    return c_address, tx


def start_contract_tx(c_address, c_data, chain_cur, account_cur, outputs=None,
                      from_group=C.ANT_UNKNOWN, gas_price=None, retention=10800):
    gas_price = gas_price if gas_price else V.COIN_MINIMUM_PRICE
    assert gas_price >= V.COIN_MINIMUM_PRICE, 'Too low gas price {}>={}'.format(gas_price, V.COIN_MINIMUM_PRICE)
    # TXを作成
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    message = bjson.dumps((c_address, c_data))
    start_tx = TX(tx={
        'version': __chain_version__,
        'type': C.TX_START_CONTRACT,
        'time': now,
        'deadline': now + retention,
        'inputs': list(),
        'outputs': outputs or list(),
        'gas_price': gas_price,
        'gas_amount': 1,
        'message_type': C.MSG_BYTE,
        'message': message})
    check_output_format(start_tx.outputs)
    start_tx.gas_amount = start_tx.getsize() + 96
    start_tx.serialize()
    # 全てのUnspentを取得
    unspent_pairs, orphan_pairs = get_unspent(chain_cur=chain_cur, account_cur=account_cur)
    unspents = full_unspents(unspent_pairs, chain_cur)
    # Emulateし、finish txにかかるGasを計算
    start_tx.height = max_block_height(chain_cur) + 1
    finish_tx, estimate_gas = create_finish_tx(start_tx=start_tx, cur=chain_cur, set_limit=False)
    start_tx.height = None
    # input/outputを補充
    # additional_fee = estimate_gas + finish_tx.getsize()
    additional_fee = int(1.5*estimate_gas + finish_tx.getsize())
    input_address = fill_inputs_outputs(start_tx, unspents, chain_cur, additional_fee=additional_fee)
    # RedeemDummyAddressを入れ替え
    new_redeem_address = replace_redeem_dummy_address(start_tx, account_cur)
    # Account間の移動をログに記録
    start_tx.serialize()
    recode_account_movement(start_tx, new_redeem_address, from_group, chain_cur, account_cur)
    # 署名をする
    setup_signature(start_tx, input_address)
    return start_tx
