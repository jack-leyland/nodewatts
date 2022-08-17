from nodewatts.subprocess_manager import NWSubprocessError, SubprocessManager
import nodewatts.log as log
from nodewatts.db import DatabaseError
from nodewatts.nwengine.__main__ import run_engine, EngineError
from nodewatts.viz_server import server as viz
from nodewatts.cgroup import CgroupInterface
from nodewatts.db import Database
from nodewatts.sensor_handler import SensorHandler
from nodewatts.profiler_handler import ProfilerHandler
from nodewatts.config import NWConfig, InvalidConfig
from nodewatts.error import NodewattsError
import os
import sys
import argparse
import json
import errno
import shutil
import logging
import traceback
import signal
import pgrep
logger = None


# Simple solution for gracefully cleaning up any changes made to system directories
# in the case of a SIGINT or SIGTERM
# Note that when smartwatts is run, its own term_handler will take over
# handling of these signals. However, a called to the below term_handler
# will still be made to cleanup the tmp directory
global_state = []
tmpPath = os.path.join(NWConfig.dirs.site_data_dir, 'tmp')


def term_handler(signum, frame):
    nw_logger = logging.getLogger("Main")
    nw_logger.info("Shutdown Requested.")
    global_cleanup()
    sys.exit(0)


def global_cleanup():
    nw_logger = logging.getLogger("Main")
    nw_logger.info("Performing Cleanup.")
    if len(global_state) > 0:
        for instance in global_state:
            instance.cleanup()
    if os.path.exists(tmpPath):
        shutil.rmtree(tmpPath)
    # Unexpected crashes sometimes leave sensor running, this will catch those cases
    pids = pgrep.pgrep("nodewatts-hwpc-sensor")
    for pid in pids:
        SubprocessManager.kill_process_tree(pid)


signal.signal(signal.SIGINT, term_handler)
signal.signal(signal.SIGTERM, term_handler)


def create_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='NodeWatts: Power profiling tool for NodeJS web servers')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Run with debug flag")
    parser.add_argument('--visualizer', '-V', action='store_true',
                        help="Start up visulization server only")
    parser.add_argument('--config_file', type=str,
                        required=True, help="Path to configuration file")
    return parser


def validate_module_configs(config: NWConfig) -> None:
    if not os.path.exists(config.sensor_config_path):
        logger.error("Sensor config file missing at path: " +
                     config.sensor_config_path)
        sys.exit(1)
    if not os.path.exists(config.sw_config_path):
        logger.info("No smartwatts configuration detected. Configuring...")
        proc = SubprocessManager(config)
        try:
            stdout, stderr = proc.nodewatts_process_blocking("sh resources/bin/smartwatts-autoconfig.sh "
                                                             + os.path.join(NWConfig.dirs.site_config_dir, "smartwatts_config.json"))
        except NWSubprocessError as e:
            logger.error(
                "Failed to run smartwatts config script. Error:" + str(e))
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
        global_state.extend([profiler, cgroup, sensor])
        profiler.setup_env()
        cgroup.create_cgroup()
        server_pid = profiler.start_server()
        cgroup.add_PID(server_pid)
        sensor.start_sensor()
        profiler.run_test_suite()
        profiler.cleanup()
        global_state.remove(profiler)
        sensor.cleanup()
        global_state.remove(sensor)
        cgroup.cleanup()
        global_state.remove(cgroup)
    except NodewattsError as e:
        global_cleanup()
        sys.exit(1)
    except Exception as e:
        logger.critical("FATAL - Unexpected error. Unable to guarentee resource cleanup. "
                        + "Please ensure your entry file contains no NodeWatts code and "
                        + "the system perf_event cgroup is removed before running again. ")
        logger.critical(traceback.format_exc())
        global_cleanup()
        sys.exit(1)
    else:
        if profiler.fail_code is not None:
            logger.error(
                "Web server exited unexpectedly - unable to contine. Run again in verbose mode to inspect error.")
            sys.exit(1)
        if sensor.fail_code is not None:
            logger.error(
                "Sensor exited unexpectedly - unable to contine. Run again in verbose mode to inspect error.")
            sys.exit(1)

        config.engine_conf_args["profile_title"] = profiler.profile_title
        config.engine_conf_args["sensor_start"] = sensor.start_time
        config.engine_conf_args["sensor_end"] = sensor.end_time


def run(config: NWConfig):
    validate_module_configs(config)
    config.inject_config_vars()
    with open(config.sw_config_path) as f:
        config.smartwatts_config = json.load(f)
    logger.info("Configuration Successful - Starting NodeWatts")
    db = Database(config.engine_conf_args["internal_db_uri"])
    try:
        logging.debug("Cleaning up existing raw data.")
        db.drop_raw_data()
    except DatabaseError as e:
        logger.debug("Failed to drop existing raw data from previous sessions")
        logger.error(str(e))
        sys.exit(1)

    logger.debug("Setting up temporary directory")
    try:
        os.mkdir(tmpPath)
        os.chmod(tmpPath, 0o777)
    except OSError as e:
        if e.errno == errno.EEXIST:
            shutil.rmtree(tmpPath)
            os.mkdir(tmpPath)
            os.chmod(tmpPath, 0o777)
        else:
            logger.error("Error creating temp working directory: \n" + str(e))
            sys.exit(1)
    config.tmp_path = tmpPath

    collect_raw_data(config)

    if config.sw_verbose:
        logging.basicConfig(level=logging.DEBUG)

    from nodewatts.smartwatts import SmartwattsError, SmartwattsHandler
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
        run_viz_server(config.viz_port,
                       config.engine_conf_args["internal_db_uri"])


def run_viz_server(port: int, mongo_uri="mongodb://localhost:27017") -> None:
    logger.info("Starting visulization server")
    viz.run(port, mongo_uri)


def main():
    conf = NWConfig()
    parser = create_cli_parser()
    parser.parse_args(namespace=conf)
    global logger
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
    conf.populate(raw)
    if conf.visualizer:
        run_viz_server(conf.viz_port, conf.engine_conf_args["internal_db_uri"])
    else:
        run(conf)
        logger.info("Profile generated! Exiting NodeWatts...")
        sys.exit(0)


if __name__ == "__main__":
    main()
