#!/usr/bin/env python

import collections
import errno
import functools
import os
import platform
import re
import time

import psutil

from . import config
from . import log


class Machine(object):

    logger = log.get_logger()
    PidData = collections.namedtuple("PidData", ("cpu_time", "wall_time", "percent_cpu"))

    def __init__(self):
        self.config = config.dot_notation()
        self.platform_name = platform.system().lower()
        self.boot_time = psutil.boot_time()
        self.pid_history = {}

    @functools.lru_cache(maxsize=1)
    def is_desktop(self):
        """Return true if this host is a desktop system."""
        # TODO: Windows/Mac
        if self.platform_name == "linux":
            return self.is_desktop_linux()
        if self.platform_name == "darwin":
            return self.is_desktop_mac()
        if self.platform_name == "windows":
            return self.is_desktop_windows()

    def is_desktop_linux(self):
        """Return true if this host is a desktop linux system."""

        # For systemd-governed linux, chech the target:
        path_init_target = self.config.machine.linux.path_init_target

        if os.path.islink(path_init_target) and os.path.realpath(
            path_init_target
        ).endswith("graphical.target"):
            return True

        # For init governed linux, check the /etc/inittab:
        path_inittab = self.config.machine.linux.path_inittab
        path_inittab_default = self.config.machine.linux.path_inittab_default
        with open(path_inittab) as fh:
            for line in fh.readlines():
                if line.startswith(path_inittab_default):
                    return True

        return False

    def is_user_logged_in_linux(self):
        """Return True if a user is currently logged in."""
        display_nums = []
        try:
            regex = re.compile(r"X(\d+)")
            displays_path = self.config.machine.linux.displays_path
            for displays in os.listdir(displays_path):
                m = regex.match(displays)
                if not m:
                    continue
                display_nums.append(int(m.group(1)))
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

        if display_nums:
            user_sessions = psutil.users()
            for user_session in user_sessions:
                for display_num in display_nums:
                    if "(:{})".format(
                        display_num
                    ) == user_session.terminal and user_session.name in (
                        "(unknown)",
                        "unknown",
                    ):
                        self.logger.warn(
                            "User {} logged into display :{}".format(
                                user_session.name, display_num
                            )
                        )
                        return True

            return False

        # These process names imply a user is logged in.
        names = ("kdesktop", "gnome-session", "startkde", "gnome-shell")

        for proc in psutil.process_iter():
            proc_name = proc.name()
            for name in names:
                if name in proc_name:
                    return True

        return False

    def _rss_update_pid(self, process, rss=0, vms=0, pcpu=0):
        """Update rss and maxrss for a running frame."""

        now = time.time()

        with process.oneshot():
            # utime, stime, cutime, cstime = process.cpu_times()
            cpu_time = sum(process.cpu_times())
            memory_info = process.memory_info()
            rss += memory_info.rss
            vms += memory_info.vms
            create_time = process.create_time()

        wall_time = now - create_time

        if process.pid in self.pid_history:
            prior = self.pid_history[process.pid]
            if wall_time != prior.wall_time:
                percent_cpu = (cpu_time - prior.cpu_time) / (wall_time - prior.wall_time)
                pcpu += (prior.percent_cpu + percent_cpu) / 2  # %cpu
                pid_data[process.pid] = self.PidData(cpu_time, wall_time, pcpu)

        for child in process.children():
            rss, vms, pcpu = self._rss_update_pid(child, rss=rss, vms=vms, pcpu=pcpu)

        return rss, vms, pcpu


    def rss_update(self, frames):
        """Update rss and maxrss for running frames."""
        if self.platform != "linux":
            return

        values = frames.values()
        for frame in values:
            if frame.pid > 0:
                process = psutil.Process(frame.pid)
                self._rss_update_frame(process)
