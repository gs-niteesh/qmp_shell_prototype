"""
QEMU qtest protocol
"""

import asyncio
from typing import (
    Awaitable,
    List,
    Optional,
    Sequence,
    Tuple,
)

from error import DisconnectedError, StateError
from util import create_task
from protocol import AsyncProtocol


class QtestError(Exception):
    def __init__(self, status: str, reason: str):
        super().__init__(status, reason)
        self.status = status
        self.reason = reason

    def __str__(self) -> str:
        ret = f"qtest command failed ({self.status})"
        if self.reason:
            ret += f" ({self.reason})"
        return ret


class QtestProtocol(AsyncProtocol[Sequence[str]]):

    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__(name)

        # Incoming async messages
        self._async_queue: asyncio.Queue[Sequence[str]] = asyncio.Queue()

        # Callers waiting for a response to an execution
        self._pending: List[
            Tuple[asyncio.Future[Sequence[str]], asyncio.Queue[Sequence[str]]]
        ] = []

    async def _new_session(self, coro: Awaitable[None]) -> None:
        self._async_queue = asyncio.Queue()
        await super()._new_session(coro)

    def _cleanup(self) -> None:
        super()._cleanup()
        assert not self._pending
        self._async_queue = asyncio.Queue()

    async def _bh_disconnect(self) -> None:
        await super()._bh_disconnect()

        if self._pending:
            self.logger.debug("Canceling pending executions")
        for fut, _queue in self._pending:
            self.logger.debug("Cancelling execution")
            # NB: This signals cancellation, but doesn't fully quiesce.
            #     FIXME: Is this a bug? what guarantees pending is empty?
            # NB2: Python 3.9 adds a msg= parameter that would be useful.
            fut.cancel()

    async def _on_message(self, msg: Sequence[str]) -> None:
        # See also protocol._on_message()

        if msg[0] == 'IRQ':
            await self._async_queue.put(msg)
            return

        # FIFO; note that the waiter removes itself from the queue.
        _fut, queue = self._pending[0]
        await queue.put(msg)

    def _cb_outbound(self, msg: Sequence[str]) -> Sequence[str]:
        # See also protocol._cb_outbound()
        self.logger.debug("--> %s", " ".join(msg))
        return msg

    def _cb_inbound(self, msg: Sequence[str]) -> Sequence[str]:
        # See also protocol._cb_inbound()
        self.logger.debug("<-- %s", " ".join(msg))
        return msg

    async def _do_recv(self) -> List[str]:
        # See also protocol._do_recv()
        msg_bytes = await self._readline()
        msg = msg_bytes.decode('utf-8').strip().split(' ')
        return msg

    def _do_send(self, msg: Sequence[str]) -> None:
        # See also protocol._do_send()
        assert self._writer is not None
        msg_str = " ".join(msg) + "\n"
        self._writer.write(msg_str.encode('utf-8'))

    # async def connect(self, address, ssl) -> None: ...
    # async def disconnect(self) -> None: ...

    async def _bh_execute(self, msg: Sequence[str],
                          queue: 'asyncio.Queue[Sequence[str]]'
                          ) -> Sequence[str]:
        """
        Execute a QMP Message and wait for the result.

        :param msg: Message to execute.
        :param queue: The queue we should expect to see a reply delivered to.

        :return: Execution result from the server.
                 The type depends on the command sent.
        """
        if not self.running:
            raise StateError("QMP is not running.")
        assert self._outgoing

        self._outgoing.put_nowait(msg)
        reply_msg = list(await queue.get())

        status = reply_msg.pop(0)
        if status in ('FAIL', 'ERR'):
            raise QtestError(status, " ".join(reply_msg))

        if status != 'OK':
            raise Exception("Unknown response: " + " ".join(reply_msg))

        return reply_msg

    async def execute(self, cmd: str, *args: str) -> Sequence[str]:
        """
        Execute a qtest command and await execution response.

        :param cmd: qtest command name.
        :param *args: Arguments (if any).

        :return: Execution response from the server.
        """
        msg = [cmd] + list(args)
        if self.disconnecting:
            raise StateError("Qtest is disconnecting/disconnected."
                             " Call disconnect() to fully disconnect.")

        queue: asyncio.Queue[Sequence[str]] = asyncio.Queue(maxsize=1)
        task = create_task(self._bh_execute(msg, queue))
        work_item = (task, queue)
        self._pending.append(work_item)

        try:
            result = await task
        except asyncio.CancelledError as err:
            raise DisconnectedError("Disconnected") from err
        finally:
            self._pending.remove(work_item)

        return result
