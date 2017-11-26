
"""TSD File API client."""

import requests

from config import ENV


def lazy_reader(filename, chunksize):
    with open(filename, 'rb+') as f:
        while True:
            data = f.read(chunksize)
            if not data:
                break
            else:
                yield data


def lazy_stdin_handler(fileinput, chunksize):
    while True:
        chunk = fileinput.read(chunksize)
        if not chunk:
            break
        else:
            yield chunk


def streamfile(env, pnum, filename, token,
               chunksize=4096, custom_headers=None):
    """
    Idempotent, lazy data upload from files.

    Parameters
    ----------
    env: str - 'test' or 'prod'
    pnum: str - project number
    filename: path to file
    token: JWT
    chunksize: bytes to read per chunk
    custom_headers: header controlling API data processing

    Returns
    -------
    str (HTTP status message)

    """
    url = '%s/%s/files/stream' % (ENV[env], pnum)
    headers = {'Authorization': 'Bearer ' + token, 'Filename': filename}
    if custom_header is not None:
        new_headers = headers.copy()
        new_headers.update(custom_headers)
    else:
        new_headers = headers
    print 'PUT: %s' % url
    resp = requests.put(url, data=lazy_reader(filename, chunksize),
                         headers=new_headers)
    return resp.text


def streamstdin(env, pnum, fileinput, filename, token,
                chunksize=4096, custom_headers=None):
    """
    Idempotent, lazy data upload from stdin.

    Parameters
    ----------
    env: str - 'test' or 'prod'
    pnum: str - project number
    filename: path to file
    token: JWT
    chunksize: bytes to read per chunk
    custom_headers: header controlling API data processing

    Returns
    -------
    str (HTTP status message)

    """
    url = '%s/%s/files/stream' % (ENV[env], pnum)
    headers = {'Authorization': 'Bearer ' + token, 'Filename': filename}
    if custom_header is not None:
        new_headers = headers.copy()
        new_headers.update(custom_headers)
    else:
        new_headers = headers
    print 'PUT: %s' % url
    resp = requests.put(url, data=lazy_stdin_handler(fileinput, chunksize),
                         headers=new_headers)
    return resp.text
