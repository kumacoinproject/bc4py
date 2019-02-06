from bc4py.utils import ProgressBar
from bc4py.user.tools import create_unoptimized_plots, convert_optimize_plot
from concurrent.futures import ProcessPoolExecutor, as_completed
from time import time, sleep
import requests

"""
plotting tool for proof of capacity
"""


def ask(what, default):
    arg = input('{}? default="{}" >'.format(what, default)) or default
    print('comment: select', arg)
    return arg


def process(b_address, start, end, path):
    create_unoptimized_plots(b_address, start, end, path)
    convert_optimize_plot(b_address, start, end, path)
    return start, end


def main(size=65536, num=4):
    # total: 65536 x 4 x 4kb = 1GB
    sleep(1)
    url = ask('url', '127.0.0.1:3000')
    username = ask('username', 'user')
    password = ask('password', 'password')
    try:
        r = requests.get(
            url='http://{}/private/newaddress?account=@Mining'.format(url),
            auth=(username, password))
    except Exception as e:
        print('error:', e)
        return
    if r.status_code != 200:
        print('error: Status code is {}'.format(r.status_code))
        return
    print("comment: success node connection.")
    address = r.json()['address']
    print('comment: plot address is {}'.format(address))
    b_address = address.encode()
    path = ask('path', 'plots')
    while True:
        size = int(ask('size', size))
        num = int(ask('num', num))
        total_size = round(size * num * 4 / 1024 / 1024, 3)
        print('comment: total size is {}GB'.format(total_size))
        if ask('OK', 'yes') in ('OK', 'ok', 'true', 'True', 'Yes', 'yes', 'Y', 'y'):
            print('comment: generate plot file.')
            break
        else:
            print('comment: User input "No" signal, retry.')
            continue
    max_workers = int(ask('workers', 1))
    futures = list()
    s = time()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        with ProgressBar('plotting', total=num) as pb:
            pb.print_progress_bar(0, 'start plotting...')
            for i in range(num):
                start = i * size
                end = (i + 1) * size
                futures.append(executor.submit(process, b_address, start, end, path))
                sleep(10)
            pb.print_progress_bar(0, 'waiting plot result...')
            for i, f in enumerate(as_completed(futures)):
                start, end = f.result()
                pb.print_progress_bar(i, 'finish from {} to {} nonce'.format(start, end))
    print('comment: all task complete {}Sec {}GB'.format(int(time()-s), total_size))


if __name__ == '__main__':
    main(size=4096, num=8)
