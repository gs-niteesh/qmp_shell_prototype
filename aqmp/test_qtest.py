#!/usr/bin/env python3

import argparse
import asyncio
import logging
from typing import Tuple, Union

from qtest_protocol import QtestProtocol, QtestError
from qtest_api import Qtest
from error import ConnectError
from util import asyncio_run


async def async_main(address: Union[str, Tuple[str, int]]) -> None:
    server = QtestProtocol()
    qtest = Qtest(server)

    # Should do nothing at all
    await server.disconnect()

    try:
        await server.connect(address)
    except ConnectError as err:
        print(str(err))
        return

    print(await qtest.endianness())

    val_a = await qtest.read(0x00, 16)
    val_b = await qtest.b64read(0x00, 16)
    assert val_a == val_b

    print(val_a)

    addr = 3*1024*1024*1024
    print(await qtest.read(addr, 16))
    await qtest.write(addr, b'hello world')
    print(await qtest.read(addr, 16))
    await qtest.write(addr, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
    print(await qtest.read(addr, 16))

    await qtest.b64write(addr, b'hello world')
    print(await qtest.b64read(addr, 16))

    try:
        await qtest.module_load('block-', 'iscsi')
    except QtestError as err:
        print(err)

    while server.running:
        print("doing nothing in particular ...")

        # FIXME: It's not clear to me right now what the right paradigm should
        # be if the bottom half closes asynchronously without our knowledge.
        #
        # The next time we go to interact with connect/disconnect/execute
        # we can obviously raise the error, but maybe we want the ability
        # to signal a disconnection event as well?
        #
        # For now, use a hacky heuristic to detect the condition,
        # then use disconnect() to retrieve the exception.
        await asyncio.sleep(1)

    await server.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="AQTest sandbox")
    parser.add_argument(
        'address', nargs='?', default='127.0.0.1:1234',
        help='e.g. "127.0.0.1:4444" or "/path/to/sock.file"',
    )
    args = parser.parse_args()

    address: Union[str, Tuple[str, int]]
    components = args.address.split(':')
    if len(components) == 2:
        address = (components[0], int(components[1]))
    else:
        # Assume UNIX socket path
        address = args.address

    asyncio_run(async_main(address))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
