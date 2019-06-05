#!/usr/bin/env python
"""gRPC service for asyncrqd."""

import asyncio

from asyncrqd.proto import rqd_grpc
from asyncrqd.proto import rqd_pb2

from asyncrqd import config
from asyncrqd import log

from grpclib.client import Channel


async def main():
    channel = Channel('127.0.0.1', 50051)
    iface = rqd_grpc.RqdInterfaceStub(channel)

    # rqd_pb2.RqdStaticLaunchFrameRequest
    # rqd_pb2.RqdStaticLaunchFrameResponse

    frameNum = "0001"
    runFrame = rqd_pb2.RunFrame()
    runFrame.resource_id = "8888888877777755555"
    runFrame.job_id = "SD6F3S72DJ26236KFS"
    runFrame.job_name = "edu-trn_jwelborn-jwelborn_teapot_bty"
    runFrame.frame_id = "FD1S3I154O646UGSNN{}".format(frameNum)
    runFrame.frame_name = "{}-teapot_bty_3D".format(frameNum)
    runFrame.command = """/usr/bin/python -c "import time;print('hello world');time.sleep(5);print('exiting {}');";""".format(int(frameNum))
    runFrame.user_name = "donal"
    runFrame.log_dir = "/mcp" # This would be on the shottree
    runFrame.show = "testing"
    runFrame.shot = "A000_0010"
    runFrame.uid = 10164
    runFrame.num_cores = 100


    reply: rqd_pb2.RqdStaticLaunchFrameResponse = await iface.LaunchFrame(rqd_pb2.RqdStaticLaunchFrameRequest(run_frame=runFrame))
    channel.close()


if __name__ == '__main__':
    asyncio.run(main())
