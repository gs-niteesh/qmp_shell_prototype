import sys
import urwid
import asyncio
import logging
import signal

from blinker import Signal
from aqmp.message import Message
from aqmp.qmp_protocol import QMP
from aqmp.error import ConnectError

statusbar_update = Signal()

address = ()

logging.basicConfig(filename='log.txt', level=logging.DEBUG)

class ExitAppError(Exception):
    pass

class StatusBar(urwid.Text):
    def __init__(self, text=''):
        super().__init__(text)
        statusbar_update.connect(self.update_text)

    def update_text(self, sender, updated_text=''):
        self.set_text(updated_text)

class Window(urwid.Frame):
    def __init__(self, body, header=None, footer=None):
        footer = StatusBar('Connected to {address}')
        super().__init__(body, header, footer)

class App(QMP):
    def __init__(self):
        super().__init__()
        self.on_event(self.add_to_list)
        self.server_disconnected = False

        self.flows = urwid.SimpleFocusListWalker([])
        self.history = urwid.ListBox(self.flows)
        self.window = Window(self.history)

        self.aloop = asyncio.get_event_loop()
        self.aloop.set_debug(True)
        event_loop = urwid.AsyncioEventLoop(loop=self.aloop)
        self.loop = urwid.MainLoop(self.window,
                                   unhandled_input=self.unhandled_input,
                                   event_loop=event_loop)

        cancel_signals = [signal.SIGTERM, signal.SIGINT]
        for sig in cancel_signals:
            self.aloop.add_signal_handler(sig, self.kill_app)

    async def _do_recv(self):
        try:
            msg = await super()._do_recv()
        except EOFError as err:
            logging.debug('Received EOF')
            # TODO: How to handle EOFError?
            msg = None
        return msg

    def unhandled_input(self, key):
        if key == 'esc':
            self.kill_app()

    def kill_app(self):
        asyncio.create_task(self._kill_app())

    async def _kill_app(self):
        # It is ok to call disconnect even in disconnect state
        await self.aloop.create_task(self.disconnect())
        logging.info('disconnect finished, Exiting app')
        raise ExitAppError()

    async def add_to_list(self, qmp, event):
        self.flows.append(urwid.Text(f'{event}'))
        if self.flows:
            self.flows.set_focus(len(self.flows) - 1)
        if event['event'] == 'SHUTDOWN':
            statusbar_update.send(self, updated_text='Server shutdown')

    async def connect_server(self):
        try:
            await self.connect(address)
        except ConnectError as err:
            logging.debug('Cannot connect to server {type(err)}')

    def run(self):
        self.aloop.create_task(self.connect_server())
        try:
            self.loop.run()
        except ExitAppError as err:
            urwid.ExitMainLoop()
        except Exception as err:
            logging.debug(str(err))

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print ('Usage: python3 app.py IP PORT')
        sys.exit(-1)

    address = (sys.argv[1], int(sys.argv[2]))
    App().run()
