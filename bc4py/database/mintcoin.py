from bc4py.config import C, BlockChainError
from bc4py.database.builder import chain_builder, tx_builder
from expiringdict import ExpiringDict
import msgpack

setting_template = {
    "additional_issue": True,
    "change_description": True,
    "change_image": True,
    "change_address": True,
}
cashe = ExpiringDict(max_len=100, max_age_seconds=1800)


class MintCoin(object):

    def __init__(self, coin_id):
        self.coin_id = coin_id
        self.name = None
        self.unit = None
        self.digit = None
        self.address = None
        self.description = None
        self.image = None
        self.txhash = None
        self.version = 0
        self.setting = setting_template.copy()

    def __repr__(self):
        return "<MintCoin id={} {} {}>".format(self.coin_id, self.name, self.address)

    @property
    def info(self):
        if self.version == 0:
            return None
        return {
            "version": self.version,
            "coin_id": self.coin_id,
            "name": self.name,
            "unit": self.unit,
            "digit": self.digit,
            "description": self.description,
            "image": self.image,
            "txhash": self.txhash.hex(),
            "address": self.address,
            "setting": self.setting
        }

    def update(self, params, setting, txhash):
        if self.version == 0:
            self.name = params['name']
            self.unit = params['unit']
            self.digit = params['digit']
            self.address = params['address']
            self.description = params.get('description')
            self.image = params.get('image')
            if setting is not None:
                self.setting.update(setting)
        else:
            if params is not None:
                if self.setting['change_address'] and 'address' in params:
                    self.address = params['address']
                if self.setting['change_description'] and 'description' in params:
                    self.description = params['description']
                if self.setting['change_image'] and 'image' in params:
                    self.image = params['image']
            if setting is not None:
                for k in setting_template.keys():
                    if k not in setting:
                        continue
                    assert isinstance(self.setting[k], bool) and isinstance(setting[k], bool)
                    if self.setting[k] and setting[k]:  # true => true
                        pass
                    elif self.setting[k]:  # true => false
                        self.setting[k] = False
                    elif setting[k]:  # false => true
                        raise BlockChainError('Not allowed change setting to True. {}'.format(k))
                    else:  # false => false
                        pass
        self.txhash = txhash
        self.version += 1


def encode(*args):
    assert len(args) == 3
    return msgpack.packb(args, use_bin_type=True)


def decode(b):
    # [coin_id]-[params]-[setting]
    # params => dict: [name]-[unit]-[digit]-[address]-[description]-[image]
    # setting => dict:
    return msgpack.unpackb(b, raw=True, encoding='utf8')


def fill_mintcoin_status(m, best_block=None, best_chain=None, stop_txhash=None):
    assert m.version == 0, 'Already updated'
    # database
    for _, _, txhash, params, setting in chain_builder.db.read_coins_iter(coin_id=m.coin_id):
        if txhash == stop_txhash:
            return
        m.update(params=params, setting=setting, txhash=txhash)
    # memory
    if best_chain:
        _best_chain = None
    elif best_block and best_block == chain_builder.best_block:
        _best_chain = chain_builder.best_chain
    else:
        dummy, _best_chain = chain_builder.get_best_chain(best_block=best_block)
    for block in reversed(best_chain or _best_chain):
        for tx in block.txs:
            if tx.hash == stop_txhash:
                return
            if tx.type != C.TX_MINT_COIN:
                continue
            coin_id, params, setting = decode(tx.message)
            if coin_id != m.coin_id:
                continue
            m.update(params=params, setting=setting, txhash=tx.hash)
    # unconfirmed
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time):
            if tx.hash == stop_txhash:
                return
            if tx.type != C.TX_MINT_COIN:
                continue
            coin_id, params, setting = decode(tx.message)
            if coin_id != m.coin_id:
                continue
            m.update(params=params, setting=setting, txhash=tx.hash)


def get_mintcoin_object(coin_id, best_block=None, best_chain=None, stop_txhash=None):
    if best_block:
        key = (best_block.hash, stop_txhash)
        if key in cashe:
            return cashe[key]
    else:
        key = None
    m = MintCoin(coin_id=coin_id)
    fill_mintcoin_status(m=m, best_block=best_block, best_chain=best_chain, stop_txhash=stop_txhash)
    if coin_id == 0:
        m.update(
            params=C.BASE_CURRENCY, setting={k: False for k, v in setting_template.items()}, txhash=b'\x00' * 32)
    elif key:
        cashe[key] = m
    return m


def check_mintcoin_new_format(m_before, new_params, new_setting):
    assert isinstance(m_before, MintCoin)
    # check  setting flags
    if isinstance(new_setting, dict):
        for k in setting_template.keys():
            if k not in new_setting:
                continue
            if not isinstance(m_before.setting[k], bool):
                return 'Setting is bool. {}={}'.format(k, m_before.setting[k])
            if not isinstance(new_setting[k], bool):
                return 'Setting is bool. {}={}'.format(k, new_setting[k])
            if m_before.setting[k] and new_setting[k]:  # true => true
                pass
            elif m_before.setting[k]:  # true => false
                pass
            elif new_setting[k]:  # false => true
                return 'Not allowed change setting to True. {}'.format(k)
            else:  # false => false
                pass
    elif new_setting is None:
        pass
    else:
        return "setting is None or dict. {}".format(type(new_setting))
    # check new params
    if isinstance(new_params, dict):
        if m_before.version == 0:
            require_set = {'name', 'unit', 'digit', 'address'}
            new_params_set = set(new_params.keys())
            if len(require_set - new_params_set) > 0:
                return 'Lack some params. {}'.format(require_set - new_params_set)
            if not (isinstance(new_params['name'], str) and 0 < len(new_params['name']) < 20):
                return 'Not correct format. {}'.format(new_params['name'])
            if not (isinstance(new_params['unit'], str) and 0 < len(new_params['unit']) < 5):
                return 'Not correct format. {}'.format(new_params['unit'])
            if not (isinstance(new_params['digit'], int) and 0 <= new_params['digit'] <= 12):
                return 'Not correct format. {}'.format(new_params['digit'])
            else:
                pass
        else:
            if len(new_params) == 0:
                return 'No update found on params'
            for k, v in new_params.items():
                if k in ('name', 'unit', 'digit'):
                    return 'Not allowed params edit. {}=>{}'.format(k, v)
                elif k == 'address':
                    if not m_before.setting['change_address']:
                        return 'Not allowed params edit. {}=>{}'.format(k, v)
                elif k == 'description':
                    if not m_before.setting['change_description']:
                        return 'Not allowed params edit. {}=>{}'.format(k, v)
                elif k == 'image':
                    if not m_before.setting['change_image']:
                        return 'Not allowed params edit. {}=>{}'.format(k, v)
                else:
                    return 'Not found param key. {}=>{}'.format(k, v)
    elif new_params is None:
        pass
    else:
        return 'params is None or dict. {}'.format(type(new_setting))
    # additional issue
    # if new_params is None and new_setting is None:
    #    return 'new_params and new_setting is None'


__all__ = [
    "setting_template",
    "MintCoin",
    "fill_mintcoin_status",
    "get_mintcoin_object",
    "check_mintcoin_new_format",
]
