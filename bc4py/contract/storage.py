from collections import defaultdict


class Storage(defaultdict):
    def __init__(self, c_address, default_factory=None, **kwargs):
        super(Storage, self).__init__(default_factory, **kwargs)
        # check value is not None
        for k, v in kwargs.items():
            if v is None:
                raise Exception('Not allowed None value...')
        # check key type
        if len({type(k) for k in kwargs}) > 1:
            raise Exception("All key type is same {}".format([type(k) for k in kwargs]))
        self.c_address = c_address
        self.version = 0

    def __repr__(self):
        return "<Storage of {} ver={} {}>".\
            format(self.c_address, self.version, dict(self.items()))

    def marge_diff(self, diff):
        for k, v in diff.items():
            if v is None:
                del self[k]
            else:
                self[k] = v
        self.version += 1

    def export_diff(self, original_storage):
        # check value is not None
        for v in self.values():
            if v is None:
                raise Exception('Not allowed None value...')
        diff = dict()
        for key in original_storage.keys() | self.keys():
            if key in original_storage and key in self:
                if original_storage[key] != self[key]:
                    diff[key] = self[key]  # update
            elif key not in original_storage and key in self:
                diff[key] = self[key]  # insert
            elif key in original_storage and key not in self:
                diff[key] = None  # delete
        # check key type
        if len({type(k) for k in diff}) > 1:
            raise Exception("All key type is same {}".format([type(k) for k in diff]))
        return diff


class ContractStorage:
    def __init__(self, key_value=None, default_value=None):
        self.version = 0
        self.key_value = key_value if key_value else dict()
        self.default_value = default_value
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
            return self.default_value

    def get(self, key, default):
        if key in self.key_value:
            return self.key_value[key]
        return default

    def items(self):
        return self.key_value.items()

    def keys(self):
        return self.key_value.keys()

    def values(self):
        return self.key_value.values()

    def __delitem__(self, key):
        if key in self.key_value:
            del self.key_value[key]

    def __contains__(self, item):
        return item in self.key_value

    def __copy__(self):
        return self.key_value.copy()

    def __eq__(self, other):
        return self.key_value == other.key_value

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
