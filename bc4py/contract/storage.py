

class ContractStorage:
    def __init__(self, key_value=None):
        self.version = 0
        self.key_value = key_value if key_value else dict()
        self.check()

    def __repr__(self):
        return "<ContractStorage {}items>".format(len(self.key_value))

    def __setitem__(self, key, value):
        if isinstance(key, bytes) and isinstance(value, bytes):
            self.key_value[key] = value
        else:
            raise TypeError('Key-value is bytes pair. {}=>{}'.format(key, value))

    def __getitem__(self, item):
        if item in self.key_value:
            return self.key_value[item]
        else:
            return None

    def __delitem__(self, key):
        if key in self.key_value:
            del self.key_value[key]

    def __contains__(self, item):
        return item in self.key_value

    def __copy__(self):
        return self.key_value.copy()

    def marge(self, diff):
        self.check()
        updates, del_key, version = diff
        if version != self.version:
            raise TypeError('ContractStorage "version" is not correct. [{}!={}]'.format(version, self.version))
        elif not isinstance(updates, dict):
            raise TypeError('ContractStorage "updates" is not dict. {}'.format(type(updates)))
        elif not isinstance(del_key, set):
            raise TypeError('ContractStorage "del_key" is not set. {}'.format(type(del_key)))
        self.key_value.update(updates)
        for k in del_key:
            del self.key_value[k]
        self.version += 1

    def diff_dev(self, new_key_value):
        self.check()
        old = set(self.key_value)
        new = set(new_key_value)
        del_key = old - new
        updates = dict()
        for k in new & old:
            if self.key_value[k] != new_key_value[k]:
                updates[k] = new_key_value[k]
        for k in new - old:
            updates[k] = new_key_value[k]
        return updates, del_key, self.version

    def diff(self, old_key_value):
        self.check()
        old = set(old_key_value)
        new = set(self.key_value)
        del_key = old - new
        updates = dict()
        for k in new - old:
            if k not in old:
                updates[k] = self.key_value[k]
            elif self.key_value[k] != old_key_value[k]:
                updates[k] = self.key_value[k]
        return updates, del_key, self.version

    def dump(self):
        return self.key_value.copy()

    def check(self):
        for k, v in self.key_value.items():
            if not isinstance(k, bytes):
                raise TypeError('Key is int,str,bytes. {}'.format(k))
            if not isinstance(v, bytes):
                raise TypeError('Value is int,str,bytes. {}'.format(v))
