#!/usr/bin/env python

import asyncio
import contextlib
import os
import sys
from asyncrqd import process

if __name__ == "__main__":
    if os.name == 'nt':
        # On Windows, the ProactorEventLoop is necessary to listen on pipes
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

        child_watcher = process.ResourceUsageSafeChildWatcher()
        child_watcher.attach_loop(loop)
        asyncio.set_child_watcher(child_watcher)

    with contextlib.closing(loop):
        # This will only connect to the process
        e0 = os.environ.copy()
        e0["cmd_id"] = "0"
        soh0 = process.SubprocessOutputHandler("/tmp/donal_test_log.000.log")
        soh0.connect_fh(sys.stdout)
        sp0 = process.SubProcess(['/home/donal/Geek/asyncrqd/bin/hurtme', "2"], soh0, nice=10, cpu_list_arg="0,2", env=e0, cwd="/tmp/p0")
        f0 = sp0.spawn(loop, soh0)

        e1 = os.environ.copy()
        e1["cmd_id"] = "1"
        soh1 = process.SubprocessOutputHandler("/tmp/donal_test_log.001.log")
        soh1.connect_fh(sys.stdout)
        sp1 = process.SubProcess(['/home/donal/Geek/asyncrqd/bin/hurtme', "4"], soh1, nice=10, cpu_list_arg="1,3", env=e1, cwd="/tmp/p1")
        f1 = sp1.spawn(loop, soh1)

        e2 = os.environ.copy()
        e2["cmd_id"] = "2"
        soh2 = process.SubprocessOutputHandler("/tmp/donal_test_log.002.log")
        soh2.connect_fh(sys.stdout)
        sp2 = process.SubProcess(['/home/donal/Geek/asyncrqd/bin/hurtme', "6"], soh2, nice=10, cpu_list_arg="4,5", env=e2, cwd="/tmp/p2")
        f2 = sp2.spawn(loop, soh2)

        f = asyncio.gather(f0, f1, f2)
        loop.run_until_complete(f)
        print('Programs exited with: {}, {} and {}'.format(sp0.exitcode, sp1.exitcode, sp2.exitcode))
        print('Programs utime with: {}, {} and {}'.format(sp0.utime, sp1.utime, sp2.utime))
        print('Programs stime with: {}, {} and {}'.format(sp0.stime, sp1.stime, sp2.stime))
        print('Programs realtime with: {}, {} and {}'.format(sp0.realtime, sp1.realtime, sp2.realtime))
