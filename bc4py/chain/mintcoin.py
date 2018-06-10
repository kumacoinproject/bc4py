from bc4py.config import C, V
from nem_ed25519.signature import verify, sign
import bjson
from binascii import hexlify


class MintCoinObject:
    hash = None
    version = None
    binary = None
    coin_id = None
    name = None
    unit = None
    digit = None
    amount = None
    supply_before = None
    additional_issue = None
    owner = None
    image = None
    sign = None
    message = None

    def __init__(self, txhash, binary=None):
        self.hash = txhash
        if binary:
            self.binary = binary
            self.deserialize()

    def __repr__(self):
        return "<MintCoin id={} name={}>".format(self.coin_id, self.name)

    @property
    def supply(self):
        return self.supply_before + self.amount

    def getinfo(self):
        r = {
            'version': self.version,
            'hash': hexlify(self.hash).decode() if self.hash else None,
            'coin_id': self.coin_id,
            'name': self.name,
            'unit': self.unit,
            'digit': self.digit,
            'amount': self.amount,
            'supply': self.supply,
            'additional_issue': self.additional_issue,
            'owner': self.owner,
            'image': self.image,
            'message': self.message}
        return r

    def serialize(self):
        d = {
            'version': self.version,
            'coin_id': self.coin_id,
            'amount': self.amount,
            'owner': self.owner,
            'sign': self.sign}
        if self.name is not None: d['name'] = self.name
        if self.unit is not None: d['unit'] = self.unit
        if self.digit is not None: d['digit'] = self.digit
        if self.additional_issue is not None: d['additional_issue'] = self.additional_issue
        if self.image is not None: d['image'] = self.image
        if self.message is not None: d['message'] = self.message
        self.binary = bjson.dumps(d, compress=False)

    def deserialize(self):
        d = bjson.loads(self.binary)
        self.version = d['version']
        self.coin_id = d['coin_id']
        self.name = d.get('name')
        self.unit = d.get('unit')
        self.digit = d.get('digit')
        self.amount = d['amount']
        self.additional_issue = d.get('additional_issue')
        self.owner = d['owner']
        self.image = d.get('image')
        self.sign = d['sign']
        self.message = d.get('message')

    def check_param(self):
        if self.coin_id < 1:
            raise MintCoinError('coin_id is >= 1.')
        elif not isinstance(self.version, int):
            raise MintCoinError('mint version is int.')
        elif not isinstance(self.name, str):
            raise MintCoinError('name is string.')
        elif not isinstance(self.unit, str):
            raise MintCoinError('unit is string.')
        elif not isinstance(self.digit, int):
            raise MintCoinError('digit is int.')
        elif self.digit < 0 or 8 < self.digit:
            raise MintCoinError('digit is 0 to 8.')
        elif not isinstance(self.additional_issue, bool):
            raise MintCoinError('additional_issue is bool.')
        elif not self.additional_issue and 0 < self.amount:
            raise MintCoinError('Not allowed add amount. {}'.format(self.amount))
        elif not (self.owner and isinstance(self.owner, str)):
            raise MintCoinError('owner is wrong. {}'.format(self.owner))
        elif len(self.owner) != 64:
            raise MintCoinError('owner is 32 bytes pk.')
        elif self.image is not None and not isinstance(self.image, str):
            raise MintCoinError('image is string url.')
        elif not (self.sign and isinstance(self.sign, bytes)):
            raise MintCoinError('sign is wrong. {}'.format(self.sign))
        elif len(self.sign) != 64:
            raise MintCoinError('sign is 64 bytes.')
        elif self.message is not None and not isinstance(self.message, str):
            raise MintCoinError('message is string.')

    def marge(self, old_mint):
        if old_mint is None:
            self.supply_before = 0
            return
        # パラメータをマージ
        if self.name is None: self.name = old_mint.name
        if self.unit is None: self.unit = old_mint.unit
        if self.digit is None: self.digit = old_mint.digit
        if self.additional_issue is None: self.additional_issue = old_mint.additional_issue
        if self.image is None: self.image = old_mint.image
        if self.message is None: self.message = old_mint.message
        # 重要項目チェック
        if self.hash == old_mint.hash:
            raise MintCoinError('Same hash marge.')
        elif self.version != old_mint.version + 1:
            raise MintCoinError('Not correct version. [{}!={}+1]'.format(self.version, old_mint.version))
        elif self.coin_id != old_mint.coin_id:
            raise MintCoinError('Different coin_id marge.')
        elif self.additional_issue and not old_mint.additional_issue:
            raise MintCoinError('Addition is False, but make True next.')
        elif self.owner != old_mint.owner:
            raise MintCoinError('Different owner marge.')
        self.version = old_mint.version + 1
        self.supply_before = old_mint.amount + old_mint.supply_before

    def generate_sign(self, sk):
        assert self.version is not None, 'mint version error.'
        d = {
            'version': self.version,
            'coin_id': self.coin_id,
            'name': self.name,
            'unit': self.unit,
            'digit': self.digit,
            'amount': self.amount,
            'additional_issue': self.additional_issue,
            'owner': self.owner}
        binary = bjson.dumps(d, compress=False)
        self.sign = sign(msg=binary, sk=sk, pk=self.owner)

    def check_sign(self):
        d = {
            'version': self.version,
            'coin_id': self.coin_id,
            'name': self.name,
            'unit': self.unit,
            'digit': self.digit,
            'amount': self.amount,
            'additional_issue': self.additional_issue,
            'owner': self.owner}
        binary = bjson.dumps(d, compress=False)
        try:
            verify(msg=binary, sign=self.sign, pk=self.owner)
        except ValueError:
            raise MintCoinError('signature verification failed.')


def setup_base_currency_mint():
    mint = MintCoinObject(None)
    mint.coin_id = 0
    mint.version = 0
    mint.name = C.BASE_CURRENCY_NAME
    mint.unit = C.BASE_CURRENCY_UNIT
    mint.digit = V.COIN_DIGIT
    mint.amount = 0
    mint.supply_before = 2 * V.BLOCK_REWARD * (V.BLOCK_HALVING_SPAN // V.BLOCK_TIME_SPAN)
    mint.additional_issue = False
    mint.owner = None
    mint.image = None
    mint.sign = None
    mint.message = C.BASE_CURRENCY_DESCRIPTION
    return mint


class MintCoinError(Exception):
    pass
