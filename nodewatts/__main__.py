import nodewatts.nwengine.log as log
from nodewatts.nwengine.db import DatabaseError
from nodewatts.nwengine.__main__ import run_engine, EngineError
from nodewatts.viz_server import server as viz
from nodewatts.cgroup import CgroupException, CgroupInitError, CgroupInterface
from nodewatts.db import Database
from nodewatts.sensor_handler import SensorException, SensorHandler
from nodewatts.smartwatts import SmartwattsError, SmartwattsHandler
from nodewatts.profiler_handler import ProfilerException, ProfilerHandler, ProfilerInitError
from nodewatts.subprocess_manager import SubprocessManager
from nodewatts.config import NWConfig, InvalidConfig

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
    parser.add_argument('--visualizer','-V', action='store_true')
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

def collect_raw_data(config: NWConfig):
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
        sys.exit(1)
    except CgroupInitError:
        profiler.cleanup()
        sys.exit(1)
    except ProfilerException:
        profiler.cleanup()
        cgroup.cleanup()
        sys.exit(1)
    except CgroupException as e:
        profiler.cleanup()
        cgroup.cleanup()
        sys.exit(1)
    except SensorException:
        profiler.cleanup()
        cgroup.cleanup()
        sensor.cleanup()
        sys.exit(1)
    except Exception as e:
        logger.critical("FATAL - Unexpected error. Unable to guarentee resource cleanup.")
        logger.critical(str(e))
        sys.exit(1)
    else:
        if profiler.fail_code is not None:
            logger.error("Web server exited unexpectedly - unable to contine. Run again in verbose mode to inspect error.")
            sys.exit(1)
        if sensor.fail_code is not None:
            logger.error("Sensor exited unexpectedly - unable to contine. Run again in verbose mode to inspect error.")
            sys.exit(1)

        config.engine_conf_args["profile_title"] = profiler.profile_title
        config.engine_conf_args["sensor_start"] = sensor.start_time
        config.engine_conf_args["sensor_end"] = sensor.end_time

# NEED SIGINT, SIGTERM handler
# Finish reorganizinig
# Need to store profile title and start end times for sensor in the engine config before passing

def run(config: NWConfig):
    validate_module_configs(config)
    with open(config.sw_config_path) as f:      
        config.smartwatts_config = json.load(f)
    config.inject_sensor_config_vars()
    logger.info("Configuration Successful - Starting NodeWatts")
    db = Database(config.engine_conf_args["internal_db_uri"])
    try:
        logging.debug("Cleaning up existing raw data.")
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
            sys.exit(1)
    config.tmp_path = tmpPath

    collect_raw_data(config)

    if config.sw_verbose:
        logging.basicConfig(level=logging.DEBUG)

    try:
        smartwatts = SmartwattsHandler(config, db)
        smartwatts.run_formula()
    except SmartwattsError:
        sys.exit(1)

    try:
        logger.info("Generating nodewatts profile.")
        run_engine(config.engine_conf_args)
    except EngineError:
        sys.exit(1)

    try:
        logger.debug("Cleaning up raw data")
        db.drop_raw_data()
    except DatabaseError as e:
        logger.warning("Failed to drop internal raw data from db.")
        logger.warning(str(e))
    
    shutil.rmtree(tmpPath)

    if config.visualize:
        run_viz_server(config.viz_port, config.engine_conf_args["internal_db_uri"])

def run_viz_server(port: int, mongo_uri="mongodb://localhost:27017") -> None:
    logger.info("Starting visulization server")
    viz.run(port, mongo_uri)

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
    if conf.visualizer:
        run_viz_server(conf.viz_port, conf.engine_conf_args["internal_db_uri"])
    else: 
        run(conf)
        logger.info("Profile generated! Exiting NodeWatts...")
    sys.exit(0)
