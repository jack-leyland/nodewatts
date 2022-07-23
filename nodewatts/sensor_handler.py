from nodewatts.error import NodewattsError
from nodewatts.config import NWConfig
from nodewatts.subprocess_manager import NWSubprocessError, NWSubprocessTimeout, SubprocessManager

import logging
import time
import subprocess
logger = logging.getLogger("Main")

class SensorException(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)

class SensorHandler():
    def __init__(self, conf: NWConfig, manager: SubprocessManager):
        self.config_path = conf.sensor_config_path
        self.sw_config_path = conf.sw_config_path
        self.proc_manager = manager
        self.sensor_process = None
        self.pid = None
        self.fail_code = None
        
    def start_sensor(self) -> None:
        logger.debug("Starting hardware sensor.")
        cmd = "hwpc-sensor --config-file "+ self.config_path
        self.sensor_process = self.proc_manager.nodewatts_process_async(cmd)
        time.sleep(2.0)
        for i in range(0,3):
            retcode = self.sensor_process.poll()
            if retcode is not None:
                logger.error("Failed to start hwpc-sensor process. Return Code: " + str(retcode))
                raise SensorException(None)
        logger.debug("Sensor started successfully. PID: "+ str(self.sensor_process.pid))
        self.pid = self.sensor_process.pid

    def poll_sensor(self) -> int:
        return self.sensor_process.poll()
    
    def _log_sensor_output(self):
        try:
            output, _ = self.sensor_process.communicate(timeout=5)
            logger.debug("Sensor output: \n" + output)
        except subprocess.TimeoutExpired:
            logger.debug("Unable to retrieve sensor output. Killing pid.")
            self.proc_manager.kill_process_tree(self.pid)
            logger.warning("Force killed sensor process. Cannot guaretee integrity of power profile timeseries")

    # Use for clean shutdown only, cleanup will handle all other cases
    def _shutdown_sensor(self):
        logger.debug("Shutting down server.")
        self.proc_manager.terminate_process_tree(self.pid)
        self._log_sensor_output()

    def cleanup(self):
        if self.sensor_process is not None:
            if self.sensor_process.poll() is None:
                self._shutdown_sensor()
            else:
                logger.error("Unexpected sensor exit with return code: " 
                                + str(self.sensor_process.poll()))
                self._log_sensor_output()
                self.fail_code = self.sensor_process.poll()


                
            
                
            
