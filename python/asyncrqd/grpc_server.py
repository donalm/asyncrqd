#!/usr/bin/env python
"""gRPC service for asyncrqd."""

import asyncio
import uvloop

from grpclib.utils import graceful_exit
from grpclib.server import Server

from .proto import rqd_grpc
from .proto import rqd_pb2_grpc
from .proto import rqd_pb2

from .proto import report_pb2


from . import config
from . import log

print(config.get("grpc"))
grpc = None


class RqdInterface(rqd_grpc.RqdInterfaceBase):
    """Listen for gRPC calls from CueBot."""

    logger = log.get_logger()

    async def LaunchFrame(self, stream):
        """Respond to CueBot request to launch a frame."""
        request: rqd_pb2.RqdStaticLaunchFrameRequest = await stream.recv_message()
        print("===============================================")
        print('request')
        print(request)
        print('type request')
        print(type(request))
        print('dir request')
        print(dir(request))
        print("===============================================")
        print('request.run_frame')
        print(request.run_frame)
        print('type request.run_frame')
        print(type(request.run_frame))
        print('dir request.run_frame')
        print(dir(request.run_frame))
        print("===============================================")
        run_frame = request.run_frame
        self.logger.debug(
            "Received LaunchFrame",
            resource_id=run_frame.resource_id,
            job_id=run_frame.job_id,
            job_name=run_frame.job_name,
            frame_id=run_frame.frame_id,
            frame_name=run_frame.frame_name,
            layer_id=run_frame.layer_id,
            command=run_frame.command,
            user_name=run_frame.user_name,
            log_dir=run_frame.log_dir,
            show=run_frame.show,
            shot=run_frame.shot,
            job_temp_dir=run_frame.job_temp_dir,
            frame_temp_dir=run_frame.frame_temp_dir,
            log_file=run_frame.log_file,
            log_dir_file=run_frame.log_dir_file,
            start_time=run_frame.start_time,
            uid=run_frame.uid,
            num_cores=run_frame.num_cores,
            gid=run_frame.gid,
            ignore_nimby=run_frame.ignore_nimby,
            environment=run_frame.environment,
            attributes=run_frame.attributes,
        )
        await stream.send_message(rqd_pb2.RqdStaticLaunchFrameResponse())

    async def ReportStatus(self, stream):
        """Return reportStatus for this daemon."""
        request = await stream.recv_message()
        self.logger.debug("request", request=request)
        await stream.send_message(
            rqd_pb2.RqdStaticReportStatusResponse(host_report=report_pb2.HostReport())
        )

    async def GetRunningFrameStatus(self, stream):
        """RPC call to return the frame info for the given frame id"""
        self.logger.debug("Request received: getRunningFrameStatus")
        request = await stream.recv_message()
        self.logger.debug(
            "frame = self.rqCore.getRunningFrame({frame_id})", frame_id=request.frameId
        )
        """
        if frame:
            return rqd_pb2.RqdStaticGetRunningFrameStatusResponse(
                running_frame_info=frame.runningFrameInfo()
            )
        else:
            context.set_details(
                "The requested frame was not found. frameId: {}".format(request.frameId)
            )
            context.set_code(grpc.StatusCode.NOT_FOUND)
            """
        return rqd_pb2.RqdStaticGetRunningFrameStatusResponse()

    async def KillRunningFrame(self, stream):
        """RPC call that kills the running frame with the given id"""
        self.logger.debug("Request received: killRunningFrame")
        request = await stream.recv_message()
        self.logger.debug(
            "frame = self.rqCore.getRunningFrame({frame_id})", frame_id=request.frameId
        )
        """
        if frame:
            frame.kill()
        """
        await stream.send_message(rqd_pb2.RqdStaticKillRunningFrameResponse())

    async def ShutdownRqdNow(self, stream):
        """RPC call that kills all running frames and shuts down rqd"""
        self.logger.debug("Request recieved: shutdownRqdNow")
        self.logger.debug("self.rqCore.shutdownRqdNow()")
        await stream.send_message(rqd_pb2.RqdStaticShutdownNowResponse())

    async def ShutdownRqdIdle(self, stream):
        """RPC call that locks all cores and shuts down rqd when it is idle.
           unlockAll will abort the request."""
        self.logger.debug("Request recieved: shutdownRqdIdle")
        self.logger.debug("self.rqCore.shutdownRqdIdle()")
        await stream.send_message(rqd_pb2.RqdStaticShutdownIdleResponse())

    async def RestartRqdNow(self, stream):
        """RPC call that kills all running frames and restarts rqd"""
        self.logger.debug("Request recieved: restartRqdNow")
        self.logger.debug("self.rqCore.restartRqdNow()")
        await stream.send_message(rqd_pb2.RqdStaticRestartNowResponse())

    async def RestartRqdIdle(self, stream):
        """RPC call that that locks all cores and restarts rqd when idle.
           unlockAll will abort the request."""
        self.logger.debug("Request recieved: restartRqdIdle")
        self.logger.debug("self.rqCore.restartRqdIdle()")
        await stream.send_message(rqd_pb2.RqdStaticRestartIdleResponse())

    async def RebootNow(self, stream):
        """RPC call that kills all running frames and reboots the host."""
        self.logger.debug("Request recieved: rebootNow")
        self.logger.debug("self.rqCore.rebootNow()")
        await stream.send_message(rqd_pb2.RqdStaticRebootNowResponse())

    async def RebootIdle(self, stream):
        """RPC call that that locks all cores and reboots the host when idle.
           unlockAll will abort the request."""
        self.logger.debug("Request recieved: rebootIdle")
        self.logger.debug("self.rqCore.rebootIdle()")
        await stream.send_message(rqd_pb2.RqdStaticRebootIdleResponse())

    async def NimbyOn(self, stream):
        """RPC call that activates nimby"""
        self.logger.debug("Request recieved: nimbyOn")
        self.logger.debug("self.rqCore.nimbyOn()")
        await stream.send_message(rqd_pb2.RqdStaticNimbyOnResponse())

    async def NimbyOff(self, stream):
        """RPC call that deactivates nimby"""
        self.logger.debug("Request recieved: nimbyOff")
        self.logger.debug("self.rqCore.nimbyOff()")
        await stream.send_message(rqd_pb2.RqdStaticNimbyOffResponse())

    async def Lock(self, stream):
        """RPC call that locks a specific number of cores"""
        request = await stream.recv_message()
        self.logger.debug("Request recieved: lock {cores}", cores=request.cores)
        self.logger.debug("self.rqCore.lock(request.cores)")
        await stream.send_message(rqd_pb2.RqdStaticLockResponse())

    async def LockAll(self, stream):
        """RPC call that locks all cores"""
        self.logger.debug("Request recieved: lockAll")
        self.logger.debug("self.rqCore.lockAll()")
        await stream.send_message(rqd_pb2.RqdStaticLockAllResponse())

    async def Unlock(self, stream):
        """RPC call that unlocks a specific number of cores"""
        request = await stream.recv_message()
        self.logger.debug("Request recieved: unlock {cores}", cores=request.cores)
        self.logger.debug("self.rqCore.unlock(request.cores)")
        await stream.send_message(rqd_pb2.RqdStaticUnlockResponse())

    async def UnlockAll(self, stream):
        """RPC call that unlocks all cores"""
        self.logger.debug("Request recieved: unlockAll")
        self.logger.debug("self.rqCore.unlockAll()")
        await stream.send_message(rqd_pb2.RqdStaticUnlockAllResponse())

    async def GetRunFrame(self, stream):
        """RPC call that unlocks all cores"""
        request = await stream.recv_message()
        self.logger.debug("Request recieved: unlockAll")
        self.logger.debug("self.rqCore.unlockAll()")
        await stream.send_message(rqd_pb2.RqdStaticUnlockAllResponse())


async def main(*, host="127.0.0.1", port=50051, loop=None):
    """Attach a protocol to a listener on the given IP address and port."""
    server = Server([RqdInterface()])  # , loop=loop)
    with graceful_exit([server]):  # , loop=loop):
        await server.start(host, port)
        print(f"Serving on {host}:{port}")
        await server.wait_closed()


def run():
    # uvloop.install()
    asyncio.run(main(loop=uvloop))
