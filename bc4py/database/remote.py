import multiprocessing
import threading
from bc4py.database.builder import builder, tx_builder
import bc4py.database.tools as tools
import types


TYPE_GENERATOR = 'Generator'
TYPE_STOP_ITERATION = 'StopIteration'


class RemoteQue:
    def __init__(self):
        self.ques = list()
        self.i = 0

    def create(self, timeout=None):
        queue = multiprocessing.Queue()
        threading.Thread(
            target=self.accept, name="Remote {}".format(self.i),
            args=(queue, timeout)).start()
        return Interface(queue)

    @staticmethod
    def accept(que, timeout):
        generator = None
        while True:
            try:
                _class, method, args = que.get(timeout=timeout)
                if _class == 'builder':
                    data = getattr(builder, method)(*args)
                elif _class == 'tx_builder':
                    data = getattr(tx_builder, method)(*args)
                elif _class == 'tools':
                    data = getattr(tools, method)(*args)
                elif _class == 'next':
                    que.put((True, generator.__next__()))
                    continue
                else:
                    continue
                if isinstance(data, types.GeneratorType):
                    generator = data
                    que.put((False, TYPE_GENERATOR))
                else:
                    que.put(data)
            except StopIteration:
                que.put((False, TYPE_STOP_ITERATION))
                generator = None
            except Exception as e:
                que.put((False, str(e)))


class Interface:
    def __init__(self, que):
        self.que = que

    def ask(self, _class, method, *args):
        self.que.put((_class, method, args))
        result, data = self.que.get(timeout=30)
        if result:
            return data
        elif data == TYPE_GENERATOR:
            raise Exception('use ask_iter.')
        elif data == TYPE_STOP_ITERATION:
            raise Exception('use ask_iter.')
        else:
            raise Exception(data)

    def ask_iter(self, _class, method, *args):
        while True:
            self.que.put((_class, method, args))
            result, data = self.que.get(timeout=30)
            if result:
                yield data
            elif data == TYPE_GENERATOR:
                _class = 'next'
            elif data == TYPE_STOP_ITERATION:
                pass
            else:
                raise Exception(data)
