#!/user/env python3
# -*- coding: utf-8 -*-


from bc4py.config import V
from bc4py.database.create import create_db, closing
from bc4py.database.user.write import fill_keypool


def fill_key_by_multiprocessing(encrypt_key, account_db_path):
    # バックでKeyPairを補充
    V.ENCRYPT_KEY = encrypt_key
    V.DB_ACCOUNT_PATH = account_db_path
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        fill_keypool(500, cur)
        db.commit()

