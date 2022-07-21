import sys
import os
from .subprocess_manager import NWSubprocessError, SubprocessManager
from .singleton import Singleton
import logging
logger = logging.getLogger("Main")

class CgroupInterface(Singleton):
    # Performs the necessary verification and creates cgroup on initialization

    def __init__(self, manager: SubprocessManager
    ):
        logger.debug("cgroup interface started.")
        self.proc_manager = manager
        # verify that cgroup directory exists. 
        # verify that perf_event subssystem exists.
        self.cgroup_root = '/sys/fs/cgroup'
        if not os.path.exists(self.cgroup_root):
            logger.error("Could not locate cgroup directory.")
            sys.exit(1)
        if not os.path.exists(os.path.join(self.cgroup_root, 'perf_event')):
            logger.error("Failed to locate perf_event subsystem. NodeWatts requires cgroupv1 and a mounted perf_event subsystem.")
            sys.exit(1)

        try:
            self.proc_manager.perf_event_process_blocking("mkdir system")
        except NWSubprocessError as e:
            logger.error("Failed to create cgroup. Error: " + str(e))
            sys.exit(1)
        else:
            logger.debug("Cgroup created.")