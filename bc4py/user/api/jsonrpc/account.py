from bc4py.config import C, V
from bc4py.bip32 import is_address
from bc4py.database.create import create_db
from bc4py.database.account import read_name2user, create_new_user_keypair
from bc4py.user import Balance
from bc4py.user.txcreation.transfer import send_from, send_many
from bc4py.user.network.sendnew import send_newtx
from logging import getLogger


log = getLogger('bc4py')


async def sendtoaddress(*args, **kwargs):
    """
    Send an amount to a given address.

    Arguments:
        1. "address"            (string, required) The bitcoin address to send to.
        2. "amount"             (numeric or string, required) The amount in BTC to send. eg 0.1
        3. "comment"            (string, optional) A comment used to store what the transaction is for.
                                     This is not part of the transaction, just kept in your wallet.
        4. "comment_to"         (string, optional) A comment to store the name of the person or organization
                                     to which you're sending the transaction. This is not part of the
                                     transaction, just kept in your wallet.
        5. subtractfeefromamount  (boolean, optional, default=false) The fee will be deducted from the amount being sent.
                                     The recipient will receive less bitcoins than you enter in the amount field.

    Result:
        "txid"                  (string) The transaction id.
    """
    if len(args) < 2:
        raise ValueError('too few arguments num={}'.format(len(args)))
    address, amount, *options = args
    if not is_address(address, V.BECH32_HRP, 0):
        raise ValueError('address is invalid')
    amount = int(amount * pow(10, V.COIN_DIGIT))
    _comment = str(options[0]) if 0 < len(options) else None  # do not use by Yiimp
    _comment_to = str(options[1]) if 1 < len(options) else None  # do not use by Yiimp
    subtract_fee_amount = bool(options[2]) if 2 < len(options) else False

    # execute send
    error = None
    from_id = C.ANT_UNKNOWN
    coin_id = 0
    coins = Balance(coin_id, amount)
    with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = db.cursor()
        try:
            new_tx = send_from(from_id, address, coins, cur,
                               subtract_fee_amount=subtract_fee_amount)
            if send_newtx(new_tx=new_tx, outer_cur=cur):
                db.commit()
            else:
                error = 'Failed to send new tx'
                db.rollback()
        except Exception as e:
            error = str(e)
            log.debug("sendtoaddress", exc_info=True)
            db.rollback()

    # submit result
    if error:
        raise ValueError(error)
    return new_tx.hash.hex()


async def sendmany(*args, **kwargs):
    """
    Send multiple times. Amounts are double-precision floating point numbers.
    Requires wallet passphrase to be set with walletpassphrase call.

    Arguments:
        1. "fromaccount"         (string, required) DEPRECATED. The account to send the funds from. Should be "" for the default account
        2. "amounts"             (string, required) A json object with addresses and amounts
            {
              "address":amount   (numeric or string) The monacoin address is the key, the numeric amount (can be string) in MONA is the value
              ,...
            }
        3. minconf                 (numeric, optional, default=1) Only use the balance confirmed at least this many times.
        4. "comment"             (string, optional) A comment

    Result:
        "txid"                   (string) The transaction id for the send. Only 1 transaction is created regardless of
                                            the number of addresses.
    """
    if len(args) < 2:
        raise ValueError('too few arguments num={}'.format(len(args)))
    from_account, pairs, *options = args
    _minconf = options[0] if 0 < len(options) else 1  # ignore
    _comment = options[1] if 1 < len(options) else None  # ignore

    error = None
    with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = db.cursor()
        try:
            user_id = read_name2user(from_account, cur)
            send_pairs = list()
            multiple = pow(10, V.COIN_DIGIT)
            for address, amount in pairs.items():
                send_pairs.append((address, 0, int(amount * multiple)))
            new_tx = send_many(user_id, send_pairs, cur)
            if send_newtx(new_tx=new_tx, outer_cur=cur):
                db.commit()
            else:
                error = 'Failed to send new tx'
                db.rollback()
        except Exception as e:
            error = str(e)
            log.debug("sendmany", exc_info=True)
            db.rollback()

    # submit result
    if error:
        raise ValueError(error)
    return new_tx.hash.hex()


async def getaccountaddress(*args, **kwargs):
    """
    DEPRECATED. Returns the current Bitcoin address for receiving payments to this account.

    Arguments:
    1. "account"       (string, required) The account name for the address. It can also be set to the empty string "" to represent the default account. The account does not need to exist, it will be created and a new address created  if there is no account by the given name.

    Result:
    "address"          (string) The account bitcoin address
    """
    if len(args) == 0:
        raise ValueError('too few arguments num={}'.format(len(args)))
    user_name = args[0]
    with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = db.cursor()
        user_id = read_name2user(user_name, cur)
        address = create_new_user_keypair(user_id, cur)
        db.commit()
    return address


__all__ = [
    "sendtoaddress",
    "sendmany",
    "getaccountaddress",
]
