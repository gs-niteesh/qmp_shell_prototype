#!/usr/bin/env python3

import argparse
import asyncio
import logging
from typing import Tuple, Union

from qmp_protocol import QMP
from error import ConnectError
from qmp_error import ExecuteError
from message import Message
from util import asyncio_run


async def async_main(address: Union[str, Tuple[str, int]],
                     server: bool = False) -> None:
    # This is just a smoke test playground; not a real test of any kind.

    qmp = QMP()

    @qmp.on_event
    async def my_event_handler(_qmp: QMP, event: Message) -> None:
        print(f"Event: {event['event']}")

    # Should do nothing at all
    await qmp.disconnect()

    try:
        if server:
            await qmp.accept(address)
        else:
            await qmp.connect(address)
    except ConnectError as err:
        print(str(err))
        return

    print(await qmp.execute('cont'))
    print(await qmp.execute('query-block'))
    print(await qmp.execute('stop'))
    print(await qmp.execute('stop'))
    print(await qmp.execute('cont'))
    print(await qmp.execute('stop'))
    await qmp.execute('query-block')
    print(await qmp.execute('cont'))
    await qmp.execute('query-block')

    try:
        await qmp.execute('block-dirty-bitmap-add')
    except ExecuteError as err:
        print(err)

    try:
        await qmp.execute('block-dirty-bitmap-add',
                          arguments={'node': 'ide0-hd0'})
    except ExecuteError as err:
        print(err)

    try:
        await qmp.execute('block-dirty-bitmap-add',
                          arguments={'node': 'ide0-hd0',
                                     'name': 'myBitmap'})
    except ExecuteError as err:
        print(err)

    try:
        await qmp.execute('unrecognized-command')
    except ExecuteError as err:
        print(err)

    while qmp.running:
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

    await qmp.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="AQMP sandbox")
    parser.add_argument(
        'address', nargs='?', default='127.0.0.1:1234',
        help='e.g. "127.0.0.1:4444" or "/path/to/sock.file"',
    )
    parser.add_argument(
        '--server', action='store_true', default=False,
        help='await connection from QEMU instead.'
    )
    args = parser.parse_args()
    address: Union[str, Tuple[str, int]]
    components = args.address.split(':')
    if len(components) == 2:
        address = (components[0], int(components[1]))
    else:
        # Assume UNIX socket path
        address = args.address

    asyncio_run(async_main(address, args.server))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
