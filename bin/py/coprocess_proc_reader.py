#!/usr/bin/env python

import asyncio
import asyncio.subprocess
import contextlib
import json
import os
import re
import signal
import stat
import sys
import tempfile
import time

from asyncrqd import log


class StdioAdapter(object):

    def __init__(self, loop=None):
        self.reader = None
        self.writer = None

        if loop is None:
            loop = asyncio.get_event_loop()

        self.loop = loop
        self.newline_byte = b'\n'

    async def connect(self, limit=asyncio.streams._DEFAULT_LIMIT):
        await self.connect_reader(limit)
        await self.connect_writer()

    async def connect_reader(self, limit):
        self.reader = asyncio.StreamReader(limit=limit, loop=self.loop)
        protocol = asyncio.StreamReaderProtocol(self.reader, loop=self.loop)
        await self.loop.connect_read_pipe(lambda: protocol, sys.stdin)
        self.read = self.reader.read
        self.readline = self.reader.readline

    async def connect_writer(self):
        writer_transport, writer_protocol = await self.loop.connect_write_pipe(
            lambda: asyncio.streams.FlowControlMixin(loop=self.loop),
            os.fdopen(sys.stdout.fileno(), 'wb')
        )

        self.writer = asyncio.streams.StreamWriter(
            writer_transport,
            writer_protocol,
            None,
            self.loop
        )

    async def write(self, data):
        try:
            data = data.encode("utf-8")
        except:
            pass

        if not data[-1] == self.newline_byte:
            data = data + self.newline_byte

        self.writer.write(data)
        await self.writer.drain()


class ProcRaider(object):

    EOF = b''
    logger = log.get_logger()

    def __init__(self, loop):
        self.loop = loop
        self.stdio = StdioAdapter(loop)
        self.pids = set()
        self.methods = {
            "add_pid":self.add_pid,
            "remove_pid":self.remove_pid,
            "set_interval":self.set_interval,
            "shutdown":self.shutdown
        }

    async def add_pid(self, pid):
        try:
            pid = int(pid)
        except Exception:
            msg = "add_pid expected int got {}: {}".format(type(pid), pid)
            self.logger.exception(msg)
            await self.return_error(msg)
            return

        self.pids.add(pid)
        await self.stdio.write(b'{"status":"ready", "method":"add_pid"}')

    async def return_error(self, msg):
        self.stdio.write(b'err')
        rval = {"error":msg}
        try:
            await self.stdio.write(json.dumps(rval))
        except Exception as e:
            raise

    async def remove_pid(self, pid):
        try:
            pid = int(pid)
        except Exception:
            self.logger.exception("remove_pid expected int got {}: {}".format(type(pid), pid))
            return

        self.pids.remove(pid)
        await self.stdio.write('{"status":"ready", "method":"remove_pid"}')

    async def set_interval(self, interval):
        try:
            pid = int(pid)
        except Exception:
            self.logger.exception("set_interval expected int got {}: {}".format(type(interval), interval))
            return

        self.interval = interval
        await self.stdio.write('{"status":"ready", "method":"set_interval"}')

    async def shutdown(self):
        await self.stdio.write('{"status":"shutdown"}')
        self.stop()

    async def connect(self):
        await self.stdio.connect()
        await self.stdio.write('{"status":"ready"}')

    def finished(self, result):
        print(result)

    async def handle_reads(self):
        while True:
            line = await self.stdio.readline()
            if line == self.EOF:
                break
            try:
                await self.process_instruction(line)
            except Exception:
                self.logger.exception("failed to process instruction", line=line)

    async def process_instruction(self, line):
        try:
            instruction = json.loads(line.strip())
        except Exception as e:
            self.logger.exception("failed to decode instruction", line=line)

        method = instruction.get("method")
        args = instruction.get("args", [])
        kwargs = instruction.get("kwargs", {})
        if not method in self.methods:
            f = self.stdio.write(json.dumps({"unrecognised_method":str(method)}))
            f.add_done_callback(lambda x:None)
        else:
            try:
                await self.methods[method](*args, **kwargs)
            except Exception as e:
                self.logger.exception("failed to execute instruction", line=line)

    def handle_sigint(self):
        self.stop()

    def stop(self):
        self.loop.stop()
        sys.exit()



async def amain(loop):
    pr = ProcRaider(loop)
    loop.add_signal_handler(signal.SIGINT, pr.handle_sigint)
    await pr.connect()
    await pr.handle_reads()

def main():
    loop = asyncio.get_event_loop()
    with contextlib.closing(loop):
        fsd = amain(loop)
        loop.run_until_complete(fsd)

main()
