import socket
import logging


def f_already_bind(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    r = False
    try:
        s.bind(("127.0.0.1", port))
    except socket.error:
        print("Port is already in use")
        r = True
    s.close()
    return r


def set_logger(level, prefix=''):
    logger = logging.getLogger()
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(levelname)-6s] [%(threadName)-10s] [%(asctime)-24s] %(message)s')
    sh = logging.FileHandler('{}-logging.log'.format(prefix))
    sh.setLevel(level)
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    logging.info("\n\n\n\n\n\n")
    logging.info("Start program")
