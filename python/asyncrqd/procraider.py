#!/usr/bin/env python

"""
Get all the stat and status files in one hit.
The IO is faster this way, and we capture them at the same time.
As we iterate over stat files, we know which PIDs we are interested in (as the immediate child pids of rqd) so we capture two dicts:
    1: Dict keyed on PID-to-data
    2: Dict keyed on SESSION-to-pid

BUT WAIT! We ALWAYS know the SESSION before we even start, because we know the interesting pids.
So - as we parse the stat files, we can already build a list of ALL the pids we care about
As we parse the stat file, we can already be issuing requests to the threadpool to read the io data for that pid
As soon as we finish parsing the stat data we can iterate over the status blocks, building dicts only for the blocks we're interested in
As soon as we finish that, we can start parsing the results of the IO reads and add that data finally to the big effing dict
"""

import asyncio
import asyncio.subprocess
import collections
import json
import os
import re
import stat
import tempfile
import time

import contextlib

import concurrent.futures
import urllib.request


class ProcRaider(object):

    system_hertz = os.sysconf('SC_CLK_TCK')

    regex0 = re.compile("\nPid:\s+(\d+)\n")
    regex1 = re.compile(r"\n(?=Name:)")
    regex2 = re.compile(r"\b(Name:\s+.*?Pid:\s+(\d+).*?)(?=(\nName:\s|$))", re.DOTALL)

    executable = "/home/donal/Geek/asyncrqd/bin/proc_directory_reader"
    attempts = []
    attempts2 = []
    attempts3 = []
    watched_pids = {}
    historical_data = {}
    stat_keys = (
        "pid",
        "session",
        "utime",
        "stime",
        "cutime",
        "cstime",
        "num_threads",
        "start_time",
        "vsize",
        "rss",
        "cpu_num"
    )

    PID = 1
    SESSION = 6
    UTIME = 14
    STIME = 15
    CUTIME = 16
    CSTIME = 17
    NUM_THREADS = 20
    START_TIME = 22
    VSIZE = 23
    RSS = 24
    CPU_NUM = 39

    stat_indices = (
        PID -1,
        SESSION -1,
        UTIME -1,
        STIME -1,
        CUTIME -1,
        CSTIME -1,
        NUM_THREADS -1,
        START_TIME -1,
        VSIZE -1,
        RSS -1,
        CPU_NUM -1
    )

    stat_entry = collections.namedtuple("StatEntry", stat_keys)

    status = 0
    boot_time = None

    @classmethod
    def read_file(cls, filepath):
        """Return the contents of an absolute filepath."""
        with open(filepath, 'r') as fh:
            return fh.read()

    @classmethod
    async def proc_data_getter(cls, suffix):
        """
        Return a dict of the contents of the /proc/PID/<suffix> files.

        The dict will be keyed on the pid as an int.
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            pid_strings = [f for f in os.listdir("/proc/") if f.isdigit()]
            template = "/proc/{}/" + suffix
            future_to_pid = {executor.submit(cls.read_file, template.format(pid)): pid for pid in pid_strings}

            rval = {}
            for future in concurrent.futures.as_completed(future_to_pid):
                pid = int(future_to_pid[future])
                try:
                    rval[pid] = future.result().strip()
                except FileNotFoundError:
                    # Ephemeral file has gone away
                    pass
                except ProcessLookupError:
                    # Ephemeral file has gone away and thread died in an unclean fashion
                    if hasattr(exc, 'errno'):
                        errno = exc.errno
                    else:
                        errno = 'unknown'
                    exists = os.path.exists("/proc/{}".format(pid))
                    print("{} generated an exception of type '{}' errno: {}: {} exists:{}".format(pid, type(exc), errno, exc, exists))
                except Exception as exc:
                    if hasattr(exc, 'errno'):
                        errno = exc.errno
                    else:
                        errno = 'unknown'
                    print("{} generated an exception of type '{}' errno: {}: {}".format(pid, type(exc), errno, exc))

            return rval

    @classmethod
    def process_proc_pid_stat_0(cls, text):
        # Fastest
        lines = [line.strip() for line in text.strip().split("\n")]

        session_cache = {key:list() for key in cls.watched_pids.keys()}

        result = {}
        for line in lines:
            fields = line.split()
            #result[fields[0]] = zip(cls.stat_keys, (int(fields[index]) for index in cls.stat_indices))
            result[int(fields[0])] = cls.stat_entry(*(int(fields[index]) for index in cls.stat_indices))

        return result

    @classmethod
    def process_proc_pid_stat_1(cls, text):
        # Second fastest
        lines = text.strip().split("\n")
        space = " "
        return {int(line[0:line.index(space)]):cls.process_stat_entry(line) for line in lines if line.strip()}

    @classmethod
    def process_stat_entry(cls, line):
         fields = line.strip().split()

         # See "man proc"
         return {
             "session": fields[5],
             "vsize": fields[22],
             "rss": fields[23],
             # These are needed to compute the cpu used
             "utime": fields[13],
             "stime": fields[14],
             "cutime": fields[15],
             "cstime": fields[16],
             # The time in jiffies the process started
             # after system boot.
             "start_time": fields[21]
         }

    @classmethod
    def process_status_entry(cls, block):
        lines = block.strip().split("\n")
        regex = re.compile(":\s+")
        result = {}
        for line in lines:
            key, value = regex.split(line, maxsplit=1)
            result[key] = value

        result["Cpus_allowed_list"] = cls.process_cpus_allowed(result["Cpus_allowed_list"])
        result["Threads"] = int(result["Threads"])
        result["voluntary_ctxt_switches"] = int(result["voluntary_ctxt_switches"])
        result["nonvoluntary_ctxt_switches"] = int(result["nonvoluntary_ctxt_switches"])
        return result

    @classmethod
    async def raid_proc_io(cls):
        data = await cls.proc_data_getter("io")

        for pid, text in data.items():
            result = {}
            for line in text.split("\n"):
                key, value = line.split(":")
                result[key] = int(value)
            data[pid] = result

        return data

    @classmethod
    def process_cpus_allowed(cls, value):
        parts = value.strip().split(",")
        result = []
        for part in parts:
            elements = part.split("-")
            start = int(elements[0])
            end = int(elements[-1]) + 1

            result.extend(range(start, end))
        return result

    @classmethod
    def process_proc_pid_status_0(cls, text):
        # fastest
        regex = cls.regex0
        offset = 0
        text = text.strip()
        finished = False
        status_data = {}

        relevant_pids = {}

        while not finished:
            try:
                next_block_index = text.index("Name:\t""", offset+1)
                this_block = text[offset:next_block_index]
            except ValueError:
                this_block = text[offset:]
                finished = True

            matches = regex.search(this_block)
            pid = int(matches.group(1))
            status_data[pid] = cls.process_status_entry(this_block)

            offset = next_block_index

        return status_data

    @classmethod
    def process_proc_pid_status_1(cls, text):
        # second fastest
        blocks = cls.regex1.split(text.strip())
        return {int(cls.regex0.search(block).group(1)):block for block in blocks if block}

    @classmethod
    def process_proc_pid_status_2(cls, text):
        # slowest
        return {int(x[1]):x[0] for x in cls.regex2.findall(text)}

    @classmethod
    async def get_data(cls):
        # slowest
        stat_data = cls.proc_data_getter("stat")
        status_data = cls.proc_data_getter("status")
        await asyncio.wait([stat_data, status_data])
        return stat_data, status_data

    @classmethod
    def get_boot_time(cls):
        if cls.boot_time is not None:
            return cls.boot_time

        with open("/proc/stat") as fh:
            data = fh.read()
            data = data.split("btime ", 1)[1]
            btime = data.split()[0]
            cls.boot_time = int(btime)
            return cls.boot_time

    @classmethod
    async def get_filesystem_data(cls):
        boot_time = cls.get_boot_time()
        st = time.perf_counter()
        separator = "\n\n\n"
        status_data = {}

        now = time.time()
        system_uptime = now - boot_time

        proc = await asyncio.create_subprocess_exec(
            cls.executable,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        #io_data = await cls.raid_proc_io()

        stat_lines, status_lines = stdout.decode("utf-8").split(separator, 1)
        status_data = ProcRaider.process_proc_pid_status_0(status_lines)

        s = time.perf_counter()
        stat_data = ProcRaider.process_proc_pid_stat_0(stat_lines)
        e0 = time.perf_counter() - s

        cls.attempts2.append(e0)

        x = time.perf_counter() -st
        cls.attempts.append(x)

        watched_pids = {}

        resultset = {}
        _historical_data = {}

        watched_pids_set = set(watched_pids.keys())

        for data in stat_data.values():
            if not data.session in watched_pids_set:
                #continue
                pass

            pid = data.session
            if pid == 20437:
                print("PID")
            if pid == 0:
                continue

            sd = status_data.get(pid)
            if sd is None or sd["Tgid"] != sd["Pid"]:
                # Ignore threads for now
                continue


            process_data = resultset.setdefault(pid, ProcessDataPoint())

            proc_io = None#io_data.get(pid)
            if proc_io:
                process_data.read_calls = proc_io["syscr"]
                process_data.write_calls = proc_io["syscw"]
                process_data.read_bytes = proc_io["read_bytes"]
                process_data.write_bytes = proc_io["write_bytes"]

            process_data.rss += data.rss
            process_data.vsize += data.vsize
            process_data.vsize += data.vsize

            process_data.cpu_time += data.utime + data.stime + data.cutime + data.cstime
            process_data.create_time = system_uptime + (data.start_time / cls.system_hertz)
            process_data.running_time = now - process_data.create_time

            process_data.context_switches = {
                "voluntary": sd["voluntary_ctxt_switches"],
                "nonvoluntary": sd["nonvoluntary_ctxt_switches"]
            }

            if process_data.running_time:
                if pid in cls.historical_data:
                    old_cpu_time, old_running_time, old_pid_pcpu = cls.historical_data[pid]
                    if old_running_time != process_data.running_time:
                        pid_pcpu = (process_data.cpu_time - old_cpu_time) / (process_data.running_time - old_running_time)
                        process_data.pcpu = (old_pid_pcpu + pid_pcpu) / 2
                        _historical_data[pid] = (process_data.cpu_time, process_data.running_time, pid_pcpu)
                else:
                    pid_pcpu = process_data.cpu_time / process_data.running_time
                    process_data.pcpu += pid_pcpu
                    _historical_data[pid] = (process_data.cpu_time, process_data.running_time, pid_pcpu)

            process_data.ptree.append({"pid":pid, "running_time":process_data.running_time, "cpu_time":process_data.cpu_time})

            #process_data.xx += data.xx


        jake = (json.dumps(resultset, indent=4))#.keys())#[20437])

        cls.historical_data = _historical_data
        return stat_data, status_data



class ProcessDataPoint(dict):
    """Inheriting from dict gives us json serializability for free."""

    def __init__(self):
        """Constructor."""
        self["rss"] = 0
        self["max_rss"] = 0
        self["vsize"] = 0
        self["max_vsize"] = 0
        self["pcpu"] = 0
        self["cpu_time"] = 0
        self["create_time"] = 0
        self["running_time"] = 0
        self["context_switches"] = 0
        self["ptree"] = []
        self["read_calls"] = 0
        self["write_calls"] = 0
        self["read_bytes"] = 0
        self["write_bytes"] = 0

    @property
    def read_calls(self):
        return self["read_calls"]

    @read_calls.setter
    def read_calls(self, value):
        self["read_calls"] = value

    @property
    def write_calls(self):
        return self["write_calls"]

    @write_calls.setter
    def write_calls(self, value):
        self["write_calls"] = value

    @property
    def read_bytes(self):
        return self["read_bytes"]

    @read_bytes.setter
    def read_bytes(self, value):
        self["read_bytes"] = value

    @property
    def write_bytes(self):
        return self["write_bytes"]

    @write_bytes.setter
    def write_bytes(self, value):
        self["write_bytes"] = value

    @property
    def ptree(self):
        return self["ptree"]

    @ptree.setter
    def ptree(self, value):
        self["ptree"] = value

    @property
    def pcpu(self):
        return self["pcpu"]

    @pcpu.setter
    def pcpu(self, value):
        self["pcpu"] = value

    @property
    def cpu_time(self):
        return self["cpu_time"]

    @cpu_time.setter
    def cpu_time(self, value):
        self["cpu_time"] = value

    @property
    def create_time(self):
        return self["create_time"]

    @create_time.setter
    def create_time(self, value):
        self["create_time"] = value

    @property
    def running_time(self):
        return self["running_time"]

    @running_time.setter
    def running_time(self, value):
        self["running_time"] = value

    @property
    def context_switches(self):
        return self["context_switches"]

    @context_switches.setter
    def context_switches(self, value):
        self["context_switches"] = value

    @property
    def rss(self):
        return self["rss"]

    @rss.setter
    def rss(self, value):
        self["rss"] = value
        self["max_rss"] = max(value, self["max_rss"])

    @property
    def vsize(self):
        return self["vsize"]

    @vsize.setter
    def vsize(self, value):
        self["vsize"] = value
        self["max_vsize"] = max(value, self["max_vsize"])

    def __repr__(self):
        return json.dumps(self, indent=4)

    def __str__(self):
        return json.dumps(self, indent=4)

'''
We have a set of watched pids that we care about
We have a set of data
We want to get the list of pids into a set.
'''

async def amain():
    st = time.perf_counter()
    for i in range(150):
        fsd = await ProcRaider.get_filesystem_data()
    print("   first ten: {}".format(ProcRaider.attempts[0:10]))
    print("    last ten: {}".format(ProcRaider.attempts[-10:]))
    print("       first: {}".format(ProcRaider.attempts[0]))
    print("         max: {}".format(max(ProcRaider.attempts)))
    print("         min: {}".format(min(ProcRaider.attempts)))
    print("         ave: {}".format(sum(ProcRaider.attempts) / len(ProcRaider.attempts)))
    print("        last: {}".format(ProcRaider.attempts[-1]))
    print("      ave e0: {}".format(sum(ProcRaider.attempts2) / len(ProcRaider.attempts2)))
    print("       total: {}".format(time.perf_counter() - st))
    # print("      ave e1: {}".format(sum(ProcRaider.attempts3) / len(ProcRaider.attempts3)))



def main():
    loop = asyncio.get_event_loop()
    with contextlib.closing(loop):
        fsd = amain()
        loop.run_until_complete(fsd)


main()
