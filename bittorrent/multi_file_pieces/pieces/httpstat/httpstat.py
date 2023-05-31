#!/usr/bin/env python
# coding: utf-8
# References:
# man curl
# https://curl.haxx.se/libcurl/c/curl_easy_getinfo.html
# https://curl.haxx.se/libcurl/c/easy_getinfo_options.html
# http://blog.kenweiner.com/2014/11/http-request-timings-with-curl.html

from __future__ import print_function

import os
import json
import sys
import logging
import time
import subprocess
import socket
import re
from threading import Thread


logging.basicConfig(level=logging.DEBUG)


import signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError('Function call timed out')

def timeout(timeout):
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Register a signal handler for the SIGALRM signal
            signal.signal(signal.SIGALRM, timeout_handler)

            # Schedule the alarm to go off after the specified timeout
            signal.alarm(timeout)

            try:
                # Call the function that may take a long time to run
                result = func(*args, **kwargs)
                return result
            except TimeoutError:
                pass
            else:
                # Cancel the alarm if the function returns before the timeout
                signal.alarm(0)

            
        return wrapper
    return decorator

def httpstat_test_multi_thread(server_ip, server_port):
    thread_pool = []
    _max_bandwidth_test = 1
    Test_result = []
    for _ in range(_max_bandwidth_test):
        thread = Thread(target= httpstat_test, args= (server_ip, server_port, Test_result))
        thread.daemon = True
        thread.start()
        thread_pool.append(thread)
    for _ in range(_max_bandwidth_test):
        thread_pool[_].join()
    return max(list(filter(lambda x: x is not None, Test_result))) \
          if len(list(filter(lambda x: x is not None, Test_result))) > 0 else None
    

def httpstat_test(server_ip, server_port, test_result = None):
    try:
        res = _httpstat(server_ip=server_ip, server_port=server_port)
        if test_result:
            test_result.append(res)
        return res
    except TimeoutError:
        if test_result:
            test_result.append(None)
        return 0

@timeout(4)
def _httpstat(server_ip, server_port):
    
    try:
    # Check if the IP address is valid
        socket.inet_aton(server_ip)
        if not isinstance(server_port, int) or not 0 <= server_port <= 65535:
            raise ValueError
    except socket.error or ValueError:
        logging.error("The {ip}:{port} isn't valid!".format(server_ip))

    current_dir = os.path.dirname(__file__)
    cmd = "{dir}/iperf -c {ip} -p {port} -d".\
        format(dir = current_dir, ip = server_ip, port = server_port)

    logging.debug('Goes into cmd: {}'.format(cmd))

    cmd_env = os.environ.copy()
    # cmd_env.update(
    #     LC_ALL='C',
    # )

    open_process = subprocess.Popen(cmd, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True, env=cmd_env)

    out, err = open_process.communicate()

    out, err = out.decode(), err.decode()
    # logging.debug("stdout is {stdout}"
    #               .format(stdout = out))

    pattern = re.compile(r'\bBandwidth\b')
    match = pattern.search(out)
    if match:
        pattern_Mbits = re.compile(r'(\d+\.\d+)\s*Mbits/sec')
        pattern_kbits = re.compile(r'(\d+\.\d+)\s*Kbits/sec')
        match_Mbits = pattern_Mbits.search(out)
        match_kbits = pattern_kbits.search(out)
        if match_Mbits:
            speed = float(match_Mbits.group(1))
            return speed
        else:
            if match_kbits:
                speed = float(match_kbits.group(1))
                return speed / 1000
    return 0

if __name__ == '__main__':

    speed = httpstat_test(server_ip= '45.95.238.144', server_port= 6995
                     )
    print(speed)