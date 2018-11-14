from bc4py.config import V
from bc4py.database.create import closing, create_db
from bc4py.database.account import read_address2keypair
from nem_ed25519.signature import sign


def message2signature(raw, address):
    # sign by address
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        uuid, sk, pk = read_address2keypair(address, cur)
    return pk, sign(msg=raw, sk=sk, pk=pk)
