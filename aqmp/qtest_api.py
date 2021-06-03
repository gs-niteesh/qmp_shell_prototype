"""
QEMU qtest API frontend
"""

import base64
from enum import Enum
from typing import Optional

from qtest_protocol import QtestProtocol


class Endianness(str, Enum):
    BIG = "big"
    LITTLE = "little"


class Qtest:
    """
    type-safe qtest API wrapper.

    By wrapping instead of extending AQQtest, all public methods here are
    1:1 with valid protocol commands.
    """
    # pylint: disable=too-many-public-methods
    def __init__(self, server: QtestProtocol):
        self._qtest = server

    async def _out(self, cmd: str, addr: int, value: int) -> None:
        res = await self._qtest.execute(cmd, str(addr), str(value))
        # FIXME: Here and basically everywhere else in this module,
        # replace assertions with exceptions.
        # We can't control the server, of course.
        assert not res

    async def _in(self, cmd: str, addr: int) -> int:
        res = await self._qtest.execute(cmd, str(addr))
        assert len(res) == 1
        return int(res[0], base=0)

    async def _write(self, cmd: str, addr: int, value: int) -> None:
        res = await self._qtest.execute(cmd, str(addr), str(value))
        assert not res

    async def _read(self, cmd: str, addr: int) -> int:
        res = await self._qtest.execute(cmd, str(addr))
        assert len(res) == 1
        return int(res[0], base=0)

    async def irq_intercept_in(self, qom_path: str) -> None:
        res = await self._qtest.execute('irq_intercept_in', qom_path)
        assert not res

    async def irq_intercept_out(self, qom_path: str) -> None:
        res = await self._qtest.execute('irq_intercept_out', qom_path)
        assert not res

    async def set_irq_in(self, qom_path: str, name: str,
                         num: int, level: int) -> None:
        res = await self._qtest.execute('set_irq_in', qom_path, name,
                                        str(num), str(level))
        assert not res

    async def outb(self, addr: int, value: int) -> None:
        await self._out('outb', addr, value)

    async def outw(self, addr: int, value: int) -> None:
        await self._out('outw', addr, value)

    async def outl(self, addr: int, value: int) -> None:
        await self._out('outl', addr, value)

    async def inb(self, addr: int) -> int:
        return await self._in('inb', addr)

    async def inw(self, addr: int) -> int:
        return await self._in('inw', addr)

    async def inl(self, addr: int) -> int:
        return await self._in('inl', addr)

    async def writeb(self, addr: int, value: int) -> None:
        return await self._write('writeb', addr, value)

    async def writew(self, addr: int, value: int) -> None:
        return await self._write('writew', addr, value)

    async def writel(self, addr: int, value: int) -> None:
        return await self._write('writel', addr, value)

    async def writeq(self, addr: int, value: int) -> None:
        return await self._write('writeq', addr, value)

    async def readb(self, addr: int) -> int:
        return await self._read('readb', addr)

    async def readw(self, addr: int) -> int:
        return await self._read('readw', addr)

    async def readl(self, addr: int) -> int:
        return await self._read('readl', addr)

    async def readq(self, addr: int) -> int:
        return await self._read('readq', addr)

    async def read(self, addr: int, size: int) -> bytes:
        res = await self._qtest.execute('read', str(addr), str(size))
        assert len(res) == 1
        assert res[0][:2] == '0x'
        return bytes.fromhex(res[0][2:])

    async def b64read(self, addr: int, size: int) -> bytes:
        """
        Read data using base64 to transfer the data over the wire.

        This is useful for making debug/test/CI logs smaller.

        :param addr: Guest address to read data from
        :param size: Size in bytes to read

        :return: Guest data.
        """
        # b64read ADDR SIZE
        res = await self._qtest.execute('b64read', str(addr), str(size))
        assert len(res) == 1
        return base64.standard_b64decode(res[0])

    async def write(self, addr: int, data: bytes) -> None:
        """write ADDR SIZE DATA"""
        res = await self._qtest.execute(
            'write', str(addr), str(len(data)), '0x' + data.hex()
        )
        assert not res

    async def memset(self, addr: int, size: int, value: int) -> None:
        """memset ADDR SIZE VALUE"""
        res = await self._qtest.execute(
            'memset', str(addr), str(size), str(value)
        )
        assert not res

    async def b64write(self, addr: int, data: bytes) -> None:
        """
        Write data using base64 to transfer the data over the wire.

        This is useful for making debug/test/CI logs smaller.

        :param addr: Guest address to write data to
        :param data: Date to write
        """
        # b64write ADDR SIZE B64_DATA
        b64data = base64.standard_b64encode(data)
        res = await self._qtest.execute(
            'b64write', str(addr), str(len(data)), b64data.decode()
        )
        assert not res

    async def endianness(self) -> Endianness:
        """endianness"""
        res = await self._qtest.execute('endianness')
        assert len(res) == 1
        return Endianness(res[0])

    async def rtas(self, cmd: str,
                   nargs: int, args_addr: int,
                   nret: int, ret_addr: int) -> None:
        # pylint: disable=too-many-arguments
        """
        Call an RTAS function

        :param cmd: name of rtas function to call
        :param nargs: number of arguments
        :param args_addr: Guest address to read args from
        :param nret: number of return value(s)
        :param ret_addr: Guest address to write return values to
        """
        res = await self._qtest.execute(
            'rtas', cmd, str(nargs), str(args_addr), str(nret), str(ret_addr)
        )
        assert len(res) == 1
        rc = int(res[0], base=0)

        # hw/ppc/spapr_rtas.c - qtest_rtas_call
        # FIXME: Replace with better exception class that offers the rc
        if rc == -4:
            raise Exception(f"RTAS executor returned H_PARAMETER ({rc})")
        if rc != 0:
            raise Exception(f"RTAS executor returned non-zero code {rc}.")

    async def clock_step(self, ns: Optional[int] = None) -> int:
        if ns is not None:
            res = await self._qtest.execute('clock_step', str(ns))
        else:
            res = await self._qtest.execute('clock_step')
        assert len(res) == 1
        return int(res[0], base=0)

    async def clock_set(self, ns: int) -> int:
        res = await self._qtest.execute('clock_set', str(ns))
        assert len(res) == 1
        return int(res[0], base=0)

    async def module_load(self, prefix: str, libname: str) -> None:
        res = await self._qtest.execute('module_load', prefix, libname)
        assert not res
