#!/usr/bin/env python

import asyncio
import collections
import time

from . import log

class VmStatException(Exception):
    """VmStat Exception."""


class Sample(object):
    """Sample data container."""

    def __init__(self, pgout_number):
        """Constructor."""
        self.epoch_time = time.time()
        self.pgout_number = pgout_number

    def __repr__(self):
        """Return string representation."""
        return "({}, {})".format(self.epoch_time, self.pgout_number)

    def get_pgout_number(self):
        """Return the sample's page out number."""
        return self.pgout_number


class VmStat(object):
    """Parse and return gpgout number from /proc/vmstat."""

    logger = log.get_logger()
    prefix = "pgpgout "

    def __init__(self, loop):
        """Constructor."""
        self.loop = loop
        self.interval = 15
        self.sample_size = 10
        self.sample_data = collections.deque(self.sample_size)
        self.min_viable_samples = 5
        self.stopping = False

    def stop(self):
        self.stopping = True

    async def start(self):
        while True:
            await self.run()

            if self.stopping:
                break

            await asyncio.sleep(self.interval)

    def get_pgpgout_number(self):
        try:
            prefix_len = len(self.prefix)
            with open("/proc/vmstat") as vmStatFile:
                for line in vmStatFile.readlines():
                    if line[0:prefix_len] == self.prefix:
                        return int(line[prefix_len:])
        except Exception:
            self.logger.warn("Failed to open /proc/vmstat file.")

        return None

    def run(self):
        pgpgout_number = self.get_pgpgout_number()

        if pgpgout_number is None:
            self.logger.warn("Could not get pgpgout number.")
            return

        self.sample_data.append(Sample(pgpgout_number))

    def get_pgout_rate(self):
        """
        Return page out rate.
        """

        now = time.time()
        sample_data_len = len(self.sample_data)
        if sample_data_len < self.min_viable_samples:
            return 0

        weight = 1
        total_weight = weight
        weighted_sum = 0
        threshold = now - self.sample_size * self.interval - 2

        for i in range(1, sample_data_len):
            sample, prior_sample = self.sample_data[i], self.sample_data[i - 1]

            if sample.epoch_time < threshold:
                continue

            delta_pgout = sample.pgout_number - prior_sample.pgout_number
            delta_time = sample.epoch_time - prior_sample.epoch_time
            weighted_sum += weight * delta_pgout / delta_time
            total_weight += weight
            weight += 1

        return weighted_sum / (total_weight * self.interval)

    def get_recent_pgout_rate(self):
        """Return the most recent page out rate."""
        if len(self.sample_data) < 2:
            return 0

        sample, prior_sample = self.sample_data[-1], self.sample_data[-2]
        return (
            (sample.pgout_number - prior_sample.pgout_number)
            / (sample.epoch_time - prior_sample.epoch_time)
            / self.interval
        )
