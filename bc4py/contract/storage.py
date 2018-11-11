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
        if diff is None:
            return  # skip
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
