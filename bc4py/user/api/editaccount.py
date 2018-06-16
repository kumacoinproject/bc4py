from bc4py.config import C, V
from bc4py.user import CoinObject
from bc4py.database.create import closing, create_db
from bc4py.database.keylock import is_locked_database, change_encrypt_key
from bc4py.user.api import web_base
from aiohttp import web
from bc4py.utils import AESCipher


async def unlock_database(request):
    post = await web_base.content_type_json_check(request)
    old_key = V.ENCRYPT_KEY
    V.ENCRYPT_KEY = post.get('password', None)
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        if is_locked_database(db.cursor()):
            V.ENCRYPT_KEY = old_key
            return web.json_response({'result': False, 'status': 'locked'}, status=400)
        else:
            return web_base.json_res({'result': True, 'status': 'unlocked'})


async def lock_database(request):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        if is_locked_database(cur):
            return web.Response(text='Already locked database.', status=400)
        new_key = AESCipher.create_key()
        change_encrypt_key(new_key, cur)
        V.ENCRYPT_KEY = new_key
        if is_locked_database(cur):
            return web.Response(text='Failed unlock check filed.', status=400)
        db.commit()
    return web_base.json_res({'key': new_key})


async def change_password(request):
    post = await web_base.content_type_json_check(request)
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        db.isolation_level = 'EXCLUSIVE'
        cur = db.cursor()
        old_key = V.ENCRYPT_KEY
        V.ENCRYPT_KEY = post.get('old', None)
        if is_locked_database(cur):
            V.ENCRYPT_KEY = old_key
            return web.Response(text='Failed to unlock database first of all.', status=400)
        new_key = post.get('new', None)
        change_encrypt_key(new_key, cur)
        V.ENCRYPT_KEY = new_key
        if is_locked_database(cur):
            V.ENCRYPT_KEY = old_key
            return web.Response(text='Unlock success, but failed to change key.', status=400)
        db.commit()
    return web_base.json_res({'result': True})


__all__ = [
    "unlock_database",
    "lock_database",
    "change_password"
]
