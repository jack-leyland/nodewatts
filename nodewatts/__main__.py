from modules.nodewatts_data_engine.nwengine.db import DatabaseError
from modules.nodewatts_data_engine.nwengine.__main__ import run_engine, EngineError
import modules.nodewatts_data_engine.nwengine.log as log


from .cgroup import CgroupException, CgroupInitError, CgroupInterface
from .db import Database
from .sensor_handler import SensorException, SensorHandler
from .smartwatts import SmartwattsError, SmartwattsHandler
from .error import NodewattsError
from .profiler_handler import ProfilerException, ProfilerHandler, ProfilerInitError
from .subprocess_manager import SubprocessManager
from .config import NWConfig, InvalidConfig

import os
import sys
import argparse
import json
import errno
import shutil
import logging


def create_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='NodeWatts: Power profiling tool for NodeJS web servers')
    parser.add_argument('--verbose','-v', action='store_true')
    parser.add_argument('--config_file', type=str, required=True)
    return parser


def validate_module_configs(config: NWConfig) -> None:
    if not os.path.exists(config.sensor_config_path):
        logger.error("Sensor config file missing at path: " + config.sensor_config_path)
        sys.exit(1)
    if not os.path.exists(config.sw_config_path):
        logger.error("Smartwatts config file missing at path: " + config.sw_config_path)
        sys.exit(1)

    with open(config.sensor_config_path, "r") as f:
        try:
            sensor_raw = json.load(f)
        except json.decoder.JSONDecodeError:
            logger.error("Sensor config file must be in valid json format")
            sys.exit(1)
    NWConfig.validate_sensor_config(sensor_raw)

    with open(config.sw_config_path, "r") as f:
        try:
            sw_raw = json.load(f)
        except json.decoder.JSONDecodeError as e:
            logger.error("Smartwatts config file must be in valid json format")
            sys.exit(1)
    NWConfig.validate_smartwatts_config(sw_raw)

def collect_raw_data(config: NWConfig, db: Database):
    proc_manager = SubprocessManager(config)
    try:
        profiler = ProfilerHandler(config, proc_manager)
        cgroup = CgroupInterface(proc_manager)
        sensor = SensorHandler(config, proc_manager)
        server_pid = profiler.start_server()
        cgroup.add_PID(server_pid)
        sensor.start_sensor()
        profiler.run_test_suite()
        profiler.cleanup()
        sensor.cleanup()
        cgroup.cleanup()
    except ProfilerInitError:
        sys.exit(3)
    except CgroupInitError:
        profiler.cleanup()
        sys.exit(4)
    except ProfilerException:
        profiler.cleanup()
        cgroup.cleanup()
        sys.exit(3)
    except CgroupException as e:
        profiler.cleanup()
        cgroup.cleanup()
        sys.exit(4)
    except SensorException:
        profiler.cleanup()
        cgroup.cleanup()
        sensor.cleanup()
        sys.exit(5)
    except Exception as e:
        logger.critical("FATAL - Unexpected error. Unable to guarentee resource cleanup.")
        logger.critical(str(e))
        sys.exit(9)
    else:
        if profiler.fail_code is not None:
            logger.error("Web server exited unexpectedly - unable to contine. Run again in verbose mode to inspect error.")
            sys.exit(6)
        if sensor.fail_code is not None:
            logger.error("Web server exited unexpectedly - unable to contine. Run again in verbose mode to inspect error.")
            sys.exit(6)

# NEED SIGINT, SIGTERM handler
# Fix smartwatts imports

def run(config: NWConfig):
    validate_module_configs(config)
    config.smartwatts_config = json.load(config.sw_config_path)
    config.inject_sensor_config_vars()
    logger.info("Configuration Successful - Starting NodeWatts")
    db = Database(config.engine_conf_args["internal_db_uri"])
    try:
        db.drop_raw_data()
    except DatabaseError as e:
        logger.debug("Failed to drop existing raw data from previous sessions")
        logger.error(str(e))
        sys.exit(1)

    tmpPath = os.path.join(os.getcwd(), 'tmp')
    logger.debug("Setting up temporary directory")
    try:
        os.mkdir(tmpPath)
        os.chmod(tmpPath,0o777)
    except OSError as e:
        if e.errno == errno.EEXIST:
            shutil.rmtree(tmpPath)
            os.mkdir(tmpPath)
            os.chmod(tmpPath,0o777)
        else:
            logger.error("Error creating temp working directory: \n" + str(e))
            sys.exit(2)
    config.tmp_path = tmpPath

    collect_raw_data(config)

    if config.sw_verbose:
        logging.basicConfig(level=logging.DEBUG)

    try:
        smartwatts = SmartwattsHandler(config, db)
        smartwatts.run_formula()
    except SmartwattsError:
        sys.exit(6)

    logger.info("Generating nodewatts profile.")
    try:
        run_engine(config.engine_conf_args)
    except EngineError:
        sys.exit(6)

    try:
        db.drop_raw_data()
    except DatabaseError as e:
        logger.warning("Failed to drop internal raw data from db.")
        logger.warning(str(e))



if __name__ == "__main__":
    conf = NWConfig()
    parser = create_cli_parser()
    parser.parse_args(namespace=conf)
    logger = log.setup_logger(conf.verbose, "Main")
    if not NWConfig.validate_config_path(conf.config_file):
        logger.error("Config file path is invalid")
        sys.exit(1)
    try:
        raw = json.load(open(conf.config_file))
    except json.decoder.JSONDecodeError:
        logger.error("Configuration file must be in valid json format")
        sys.exit(1)
    try:
        NWConfig.validate(raw)
    except InvalidConfig as e:
        logger.error("Configuration Error: " + str(e))
        sys.exit(1)
    conf.setup(raw)
    #sys.tracebacklimit = 0
    run(conf)
    logger.info("Profile generated! Exiting NodeWatts...")
    sys.exit(0)
