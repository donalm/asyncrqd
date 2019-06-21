#!/usr/bin/env python
"""A minimal process protocol."""

import asyncio
import contextlib
import io
import locale
import os
import random
import sys
import time

from asyncrqd.proto import rqd_grpc
from asyncrqd.proto import rqd_pb2
from asyncio.unix_events import SafeChildWatcher

from asyncrqd import config
from asyncrqd import log

from grpclib.client import Channel


class FailedSubProcessException(RuntimeError):
    """When a child process returns a non-zero exit code."""

    def __init__(self, pid, exitcode):
        self.exitcode = exitcode
        self.pid = pid
        msg = "child process with pid {} exited with code {}"
        RuntimeError.__init__(self, msg.format(pid, exitcode))


class SubprocessOutputHandler(object):
    def __init__(self, logfile=None, encoding=None):
        self.encoding = encoding or locale.getpreferredencoding(False)
        self._stdout = None
        self._stderr = None
        self._files = {}
        self._fh = {}
        self._ws = {}
        if logfile is not None:
            self.connect_file(logfile)

    def connect_file(self, logfile):
        fh = open(logfile, "ab", buffering=0)
        key = self.connect_fh(fh)
        self._files[logfile] = (fh, key,)

    def connect_fh(self, fh):
        print(self._fh)

        _fh = os.fdopen(fh.fileno(), "wb", closefd=False)
        flushable = hasattr(_fh, 'flush')

        if not self._fh:
            key = 1000
        else:
            key = max([k for k in self._fh if isinstance(k, int)]) + 1
        self._fh[key] = (_fh, flushable)
        return key

    def connect_ws(self, ws):
        if not self._ws:
            key = 1000
        else:
            key = max([k for k in self._ws if isinstance(k, int)]) + 1
        self._ws[key] = ws
        return key

    def disconnect_fh(self, fh):
        return self._fh.pop(fh, None)

    def disconnect_file(self, logfile):
        fh, key = self._files.pop(logfile, None)
        self._files.pop(logfile, None)
        self.disconnect_fh(fh)

    def stderr_write(self, line):
        encoded_line = line.encode("utf-8")
        for fh, flush in self._fh.values():
            fh.write(encoded_line)
            if flush:
                fh.flush()
        for ws in self._ws.values():
            ws.sendMessage(encoded_line, False)

    def stdout_write(self, line):
        encoded_line = line.encode("utf-8")
        for fh, flush in self._fh.values():
            fh.write(encoded_line)
            if flush:
                fh.flush()
        for ws in self._ws.values():
            ws.sendMessage(encoded_line, False)

    def close(self):
        for fh in self._files.values():
            try:
                fh.close()
            except Exception:
                pass


class SubprocessProtocol(asyncio.SubprocessProtocol):
    """A minimal process protocol that processes lines of text output."""

    STDIN = 0
    STDOUT = 1
    STDERR = 2
    _c = 0

    def __init__(self, *args, loop=None, output_handler=None, linebreak="\n", **kwargs):
        """Constructor."""
        asyncio.SubprocessProtocol.__init__(self, *args, **kwargs)

        self._stdout = []
        self._stderr = []
        self._buffers = {
            self.STDOUT: self._stdout,
            self.STDERR: self._stderr,
        }

        self._handlers = {
            self.STDOUT: self._handle_stdout,
            self.STDERR: self._handle_stderr,
        }

        self._output_handler = output_handler
        self._linebreak = linebreak
        self._exited = asyncio.Future(loop=loop)
        self._transport = None
        self._pid = None
        self._start_time = None

        SubprocessProtocol._c += 1
        self._count = SubprocessProtocol._c

    @property
    def finished(self):
        return self._exited

    def pipe_data_received(self, fd, data):
        """Process a chunk of stdout/stderr from the child process."""
        data = data.decode(locale.getpreferredencoding(False))

        # Identify the correct buffer for the file descriptor
        buff = self._buffers[fd]
        buff.append(data)

        if not self._linebreak in data:
            return

        lines = "".join(buff).split(self._linebreak)
        self._buffers[fd] = [lines.pop()]
        for line in lines:
            try:
                self._handlers[fd](line + self._linebreak)
            except Exception as e:
                print("ERROR: failed to handle line on fh '{}': {}".format(fd, e))

    def connection_made(self, transport):
        """When the child process is alive, store a transport attribute."""
        asyncio.SubprocessProtocol.connection_made(self, transport)
        self._transport = transport
        self._pid = transport.get_pid()
        self._start_time = time.monotonic()
        print("CONNECTION MADE: {}".format(transport.get_pid()))

    def pipe_connection_lost(self, fd, exc=None):
        """The child process has closed stdout/stderr."""
        print("CONNECTION CLOSED ({}): {} :: {}".format(self._count, fd, exc))

    def _handle_stdout(self, line):
        """The child process printed a line to stdout."""
        self._output_handler.stdout_write(line)

    def _handle_stderr(self, line):
        """The child process printed a line to stderr."""
        self._output_handler.stderr_write(line)

    def process_exited(self):
        """The child process exited."""
        exitcode = self._transport.get_returncode()
        self._real_time = time.monotonic() - self._start_time
        resources = ResourceUsageSafeChildWatcher.watched_pids.pop(self._pid, None)
        self._exited.set_result(
            {
                "exitcode": exitcode,
                "realtime": self._real_time,
                "utime": resources.ru_utime,
                "stime": resources.ru_stime,
            }
        )


class SubProcess(object):

    _count = 0

    def __init__(self, command, soh, cwd=None, env=None, nice=None, cpu_list_arg=None):
        self.exitcode = None
        self.transport = None
        self.protocol = None
        self.resources = None
        self.output_handler = soh
        self.nice = nice
        self.cwd = cwd
        self.env = env
        self.command = command
        self.cpu_list_arg = cpu_list_arg
        self.stime = None
        self.utime = None
        self.realtime = None
        self._starttime = None

        self.id = SubProcess.next_id()

    @classmethod
    def next_id(cls):
        """Return a unique integer ID for this process."""
        _id = SubProcess._count
        SubProcess._count += 1
        return _id

    def preexec_fn(self):
        """
        This method is run in the child process immediately after fork and before exec.

        This gives us an opportunity to:
         - re-nice the child process
         - taskset the child process
         - create a new process group for the child process

        Note that uniquely, this method does not care about running asynchronously.
        We are happy to call some methods using the traditional blocking APIs
        immediately before we exec.

        Note also that we should not log in this method. We can print log information
        to stdout for the parent process to capture and log it.
        """

        try:
            if self.nice:
                os.nice(self.nice)
        except Exception as e:
            result = str(e)
            print("failed to os.nice({}): {}".format(self.nice, result))

        try:
            command = ""
            if self.cpu_list_arg:
                pid_arg = str(os.getpid())
                command = ["/usr/bin/taskset", "--all-tasks", "--cpu-list", "--pid", self.cpu_list_arg, pid_arg]
                print(" ".join(command))

                import subprocess
                p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
                stdout, stderr = p.communicate()
                exitcode = p.returncode
        except Exception as e:
            result = str(e)
            print("failed to taskset '{}': {}".format(command, result))

        os.setsid()

    def spawn(self, loop, soh):
        self.loop = loop
        command = ["/usr/bin/time", "-p", "-o", "/tmp/donaltimetest.{}".format(self.id)] + self.command

        def sp_closure():
            return SubprocessProtocol(loop=loop, output_handler=soh)

        transports = loop.run_until_complete(
            loop.subprocess_exec(sp_closure, *command, restore_signals=True, preexec_fn=self.preexec_fn, cwd=self.cwd, env=self.env)
        )
        self.transport = transports[0]
        self.protocol = self.transport.get_protocol()
        self.protocol.finished.add_done_callback(self._done)
        return self.handle_subprocess_exception(self.protocol.finished)

    def _done(self, fu):
        result = fu.result()
        self.exitcode = result.get("exitcode")
        self.realtime = result.get("realtime")
        self.utime = result.get("utime")
        self.stime = result.get("stime")

    async def handle_subprocess_exception(self, coro):
        try:
            await coro
        except Exception as e:
            print('subprocess {} failed: {}'.format(self.command, e))


class ResourceUsageSafeChildWatcher(SafeChildWatcher):
    """
    SafeChildWatcher alternative that reports resource usage.

    Replace the standard SafeChildWatcher with one that uses os.wait4 instead of
    os.waitpid, so that we can get resource usage data without having to wrap our
    child process in /usr/bin/time

    Suggested by Enrico Zini:
    https://www.enricozini.org/blog/2019/debian/getting-rusage-of-child-processes-on-python-s-asyncio/
    """

    watched_pids = {}

    def _do_waitpid(self, expected_pid):
        assert expected_pid > 0

        try:
            pid, status, resources = os.wait4(expected_pid, os.WNOHANG)
        except ChildProcessError:
            # The child process is already reaped
            # (may happen if waitpid() is called elsewhere).
            pid = expected_pid
            returncode = 255
            logger.warning(
                "Unknown child process pid %d, will report returncode 255",
                pid)
        else:
            if pid == 0:
                # The child process is still alive.
                return

            returncode = self._compute_returncode(status)
            if self._loop.get_debug():
                logger.debug('process %s exited with returncode %s',
                             expected_pid, returncode)

        ResourceUsageSafeChildWatcher.watched_pids[expected_pid] = resources

        try:
            callback, args = self._callbacks.pop(pid)
        except KeyError:  # pragma: no cover
            # May happen if .remove_child_handler() is called
            # after os.waitpid() returns.
            if self._loop.get_debug():
                logger.warning("Child watcher got an unexpected pid: %r",
                               pid, exc_info=True)
        else:
            callback(pid, returncode, *args)
