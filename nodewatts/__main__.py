import modules.nodewatts_data_engine.nwengine.log as log
from nodewatts.cgroup import CgroupInterface
from .error import NodewattsError
from .profiler_handler import ProfilerHandler
from .subprocess_manager import SubprocessManager
from .config import NWConfig, InvalidConfig
import os
import sys
import argparse
import json
import errno
import shutil


def create_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='NodeWatts: Power profiling tool for NodeJS web servers')
    parser.add_argument('--verbose','-v', action='store_true')
    parser.add_argument('--config_file', type=str, required=True)
    return parser


def validate_module_configs() -> None:
    sensor_path = os.path.join(
        os.getcwd(), "./nodewatts/config/hwpc_config.json")
    sw_path = os.path.join(
        os.getcwd(), "./nodewatts/config/smartwatts_config.json"
    )
    if not os.path.exists(sensor_path):
        logger.error("Sensor config file missing at path: " + sensor_path)
        sys.exit(1)
    if not os.path.exists(sw_path):
        logger.error("Smartwatts config file missing at path: " + sw_path)
        sys.exit(1)

    with open(sensor_path, "r") as f:
        try:
            sensor_raw = json.load(f)
        except json.decoder.JSONDecodeError:
            logger.error("Sensor config file must be in valid json format")
            sys.exit(1)
    NWConfig.validate_sensor_config(sensor_raw)

    with open(sw_path, "r") as f:
        try:
            sw_raw = json.load(f)
        except json.decoder.JSONDecodeError as e:
            logger.error("Smartwatts config file must be in valid json format")
            sys.exit(1)
    NWConfig.validate_smartwatts_config(sw_raw)

def run(config: NWConfig):
    validate_module_configs()
    config.inject_module_config_vars()
    logger.info("Configuration Successful - Starting NodeWatts")
    tmpPath = os.path.join(os.getcwd(), 'tmp')
    logger.debug("Setting up temporary directory")
    try:
        os.mkdir(tmpPath)
    except OSError as e:
        if e.errno == errno.EEXIST:
            shutil.rmtree(tmpPath)
            os.mkdir(tmpPath)
        else:
            logger.error( "Error creating temp working directory: \n" + str(e))
            sys.exit(1)
    config.tmp_path = tmpPath
    proc_manager = SubprocessManager(config)
    profiler = ProfilerHandler(config, proc_manager)
    #cgroup = CgroupInterface(proc_manager)


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
