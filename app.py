import sys
import json
import urwid
import asyncio
import logging
import signal
import urwid_readline

from blinker import Signal
from aqmp.message import Message
from aqmp.qmp_protocol import QMP
from aqmp.error import ConnectError

statusbar_update = Signal()
msg_update = Signal()
send_msg = Signal()

address = ()

logging.basicConfig(filename='log.txt', level=logging.DEBUG)

class ExitAppError(Exception):
    pass

class StatusBar(urwid.Text):
    def __init__(self, text=''):
        super().__init__(text, align='right')
        statusbar_update.connect(self.update_text)

    def update_text(self, sender, updated_text=''):
        self.set_text(updated_text)

class CustomEdit(urwid_readline.ReadlineEdit):
    def __init__(self):
        super().__init__(caption='> ', multiline=True)
        self.history = []
        self.last_index = -1;
        self.show_history = False

    def keypress(self, size, key):
        msg = self.get_edit_text()
        if key == 'up' and not msg:
            self.show_history = True
            last_msg = self.history[self.last_index] if self.history else ''
            self.set_edit_text(last_msg)
            self.last_index += 1
        elif key == 'up' and self.show_history:
            if self.last_index < len(self.history):
                self.set_edit_text(self.history[self.last_index])
                self.last_index += 1
        elif key == 'meta enter':
            send_msg.send(self, msg=msg)
            self.history.insert(0, msg)
            self.set_edit_text('')
            self.last_index = 0
            self.show_history = False
        else:
            self.show_history = False
            self.last_index = 0
            return super().keypress(size, key)

class HistoryWindow(urwid.Frame):
    def __init__(self):
        self.footer = urwid.Pile([urwid.Divider('_', 0, 0), CustomEdit(), urwid.Divider('_',0, 0)])
        self.flows = urwid.SimpleFocusListWalker([])
        self.body = urwid.ListBox(self.flows)
        super().__init__(self.body, footer=self.footer)
        msg_update.connect(self.add_to_list)

    def add_to_list(self, sender, msg):
        self.flows.append(urwid.Text(str(msg)))
        if self.flows:
            self.flows.set_focus(len(self.flows) - 1)

class Window(urwid.Frame):
    def __init__(self):
        footer = StatusBar(f'Connected to {address[0]}:{address[1]}')
        self.stack = []
        body = HistoryWindow()
        super().__init__(body, footer=footer)
        logging.debug('Window initialized')

class App(QMP):
    def __init__(self):
        super().__init__()
        self.on_event(self.add_to_list)
        self.server_disconnected = False
        self.window = Window()

        self.aloop = asyncio.get_event_loop()
        self.aloop.set_debug(True)
        event_loop = urwid.AsyncioEventLoop(loop=self.aloop)
        self.loop = urwid.MainLoop(self.window,
                                   unhandled_input=self.unhandled_input,
                                   event_loop=event_loop)

        cancel_signals = [signal.SIGTERM, signal.SIGINT]
        for sig in cancel_signals:
            self.aloop.add_signal_handler(sig, self.kill_app)
        send_msg.connect(self.send_to_server)

    async def _send_to_server(self, msg):
        try:
            msg = json.loads(str(msg))
            cmd = msg['execute']
            args = msg.get('arguments')
            response = await self.execute(cmd, args)
            logging.info('Response: %s %s', response, type(response))
            response = json.dumps(response, indent=2)
            logging.info('Response: %s %s', response, type(response))
            msg_update.send(self, msg=response)
        except Exception as e:
            logging.info('Exception from _send_to_server: %s', str(e))

    def send_to_server(self, sender, msg):
        asyncio.create_task(self._send_to_server(msg))

    def unhandled_input(self, key):
        if key == 'esc':
            self.kill_app()

    def kill_app(self):
        asyncio.create_task(self._kill_app())

    async def _kill_app(self):
        # It is ok to call disconnect even in disconnect state
        await self.disconnect()
        logging.info('disconnect finished, Exiting app')
        raise ExitAppError()

    async def add_to_list(self, qmp, event):
        msg_update.send(self, msg=event)
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
