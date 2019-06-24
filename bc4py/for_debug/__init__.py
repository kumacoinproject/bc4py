from bc4py.config import V, stream
from logging import *
import socket
import os

log = getLogger('bc4py')


def f_already_bind(port):
    """ check port already bind """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    r = False
    try:
        s.bind(("127.0.0.1", port))
    except socket.error:
        print("Port is already in use")
        r = True
    s.close()
    return r


def set_logger(level=INFO, path=None, f_remove=False):
    """
    Setup logger
    :param level: logging level.
    :param path: output log file path
    :param f_remove: remove log file when restart.
    """
    logger = getLogger()
    for sh in logger.handlers:
        logger.removeHandler(sh)
    logger.propagate = False
    logger.setLevel(DEBUG)
    formatter = Formatter('[%(levelname)-6s] [%(threadName)-10s] [%(asctime)-24s] %(message)s')
    if path:
        # recode if user sets path
        if f_remove and os.path.exists(path):
            os.remove(path)
        sh = FileHandler(path)
        sh.setLevel(level)
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    sh = StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    log.info("\n\n\n\n\n\n")
    log.info("Start program")


def stream_printer():
    log.debug("register stream print")
    stream.subscribe(on_next=log.debug, on_error=log.error)


__all__ = [
    "f_already_bind",
    "set_logger",
    "stream_printer",
]
