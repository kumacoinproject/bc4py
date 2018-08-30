from bc4py.config import C
import multiprocessing
import yespower
# import yescryptr16
# import yescryptr64
# import zny_yescrypt


def generator_process(pipe):
    print("POW hash gene start.")
    while True:
        try:
            binary = pipe.recv()
            pow_hash = yespower.hash(binary)
            pipe.send(pow_hash)
        except Exception as e:
            print("POW hash gene error:", e)
            break


class PowGenerator:
    # GCとyescryptr16の相性が悪くメモリリークする為
    def __init__(self):
        self.p = None
        self.pipe = None
        self.lock = None

    def start(self):
        pipe0, pipe1 = multiprocessing.Pipe()
        self.pipe = pipe1
        self.lock = multiprocessing.Lock()
        self.p = multiprocessing.Process(target=generator_process, args=(pipe0,))
        self.p.daemon = True
        self.p.start()

    def calc(self, binary):
        with self.lock:
            try:
                self.pipe.send(binary)
                pow_hash = self.pipe.recv()
                return pow_hash
            except BlockingIOError:
                self.start()
                self.pipe.send(binary)
                pow_hash = self.pipe.recv()
        return pow_hash

    def close(self):
        self.p.terminate()
        self.pipe.close()


# メモリリーク防止の為に別プロセスでハッシュ計算する
pow_generator = PowGenerator()


def update_work_hash(block):
    if block.flag == C.BLOCK_POS:
        proof_tx = block.txs[0]
        block.work_hash = proof_tx.get_pos_hash(block.previous_hash)
    elif block.flag == C.BLOCK_POW:
        block.work_hash = yespower.hash(block.b)
    elif block.flag == C.BLOCK_GENESIS:
        block.work_hash = b'\xff' * 32


"""
# 80bytesでないと正しくハッシュが出ない模様
        if self.flag != C.BLOCK_POW:
            pass
        elif pow_generator.p is None:
            self.work_hash = yescryptr16.getPoWHash(self.b)
        else:
            self.work_hash = pow_generator.calc(self.b)
"""