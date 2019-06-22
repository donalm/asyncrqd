#!/usr/bin/env python

import time

from . import config

class Environment(object):

    @classmethod
    def linux(cls, user_name, frame):
        dn = config.dot_notation()
        linux = {}
        linux["PATH"] = dn.environment.linux.PATH
        linux["TZ"] = time.tzname[0]

        # user_name
        linux["USER"] = user_name
        linux["MAIL"] = "/usr/mail/{}".format(user_name)
        linux["HOME"] = "/net/homedirs/{}".format(user_name)

        env = cls(linux)
        return env

    def __init__(self, platform_env, frame):

        env = platform_env.copy()
        env["TERM"] = "unknown"
        env["TZ"] = self.rqCore.machine.getTimezone()
        env["LOGNAME"] = frame.user_name
        env["MAIL"] = "/usr/mail/%s" % frame.user_name
        env["HOME"] = "/net/homedirs/%s" % frame.user_name
        env["mcp"] = "1"
        env["show"] = frame.show
        env["shot"] = frame.shot
        env["jobid"] = frame.job_name
        env["jobhost"] = self.rqCore.machine.getHostname()
        env["frame"] = frame.frame_name
        env["zframe"] = frame.frame_name
        env["logfile"] = frame.log_file
        env["maxframetime"] = "0"
        env["minspace"] = "200"
        env["CUE3"] = "True"
        env["CUE_GPU_MEMORY"] = str(self.rqCore.machine.getGpuMemory())
        env["SP_NOMYCSHRC"] = "1"

        for key in frame.environment:
            self.env[key] = frame.environment[key]

        # Add threads to use all assigned hyper-threading cores
        if 'CPU_LIST' in frame.attributes and 'CUE_THREADS' in self.env:
            self.env['CUE_THREADS'] = str(max(
                int(self.env['CUE_THREADS']),
                len(frame.attributes['CPU_LIST'].split(','))))
            self.env['CUE_HT'] = "True"


