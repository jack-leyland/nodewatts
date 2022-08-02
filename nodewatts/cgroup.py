import os
import logging

from nodewatts.error import NodewattsError
from nodewatts.subprocess_manager import NWSubprocessError, SubprocessManager

logger = logging.getLogger("Main")

class CgroupException(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)

class CgroupInitError(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)

class CgroupInterface():
    # Performs the necessary verification and creates cgroup on initialization
    # The name of the cgroup is hardcoded to "system" for compatibility with hwpc-sensor
    cgroup_name = "system"
    cgroup_root = '/sys/fs/cgroup'
    perf_root = '/sys/fs/cgroup/perf_event'
    def __init__(self, manager: SubprocessManager):
        self.proc_manager = manager
        if not os.path.exists(CgroupInterface.cgroup_root):
            logger.error("Could not locate cgroup directory.")
            raise CgroupInitError(None)
        if not os.path.exists(os.path.join(CgroupInterface.perf_root)):
            logger.error("Failed to locate perf_event subsystem. NodeWatts requires cgroupv1 and a mounted perf_event subsystem.")
            raise CgroupInitError(None)

        try:
            self.proc_manager.perf_event_process_blocking("mkdir system")
        except NWSubprocessError as e:
            logger.error("Failed to create cgroup. Error: " + str(e))
            raise CgroupInitError(None) from None
        else:
            logger.debug("cgroup created.")

    def add_PID(self, PID: int) -> None:
        path = os.path.join(CgroupInterface.perf_root, CgroupInterface.cgroup_name, "cgroup.procs")
        if not os.path.exists(path):
            logger.error("Could not locate cgroup.procs file.")
            logger.debug("Tried: " + path)
            raise CgroupException(None)
        with open(path, "a") as f:
            f.write(str(PID)+"\n")
        logger.debug("PID added to cgroup.")

    
    def cleanup(self):
        logger.debug("Removing cgroup.")
        try:
            self.proc_manager.perf_event_process_blocking("rmdir system")
        except NWSubprocessError as e:
            logger.warning("Failed to remove cgroup from perf_event directory. Error: \n" + str(e))