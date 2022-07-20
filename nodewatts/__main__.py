import modules.nodewatts_data_engine.nwengine.log as log
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
    parser.add_argument('--config_file', type=str, required=True)
    return parser


def validate_module_configs() -> None:
    sensor_path = os.path.join(
        os.getcwd(), "./nodewatts/config/hwpc_config.json")
    sw_path = os.path.join(
        os.getcwd(), "./nodewatts/config/smartwatts_config.json"
    )
    if not os.path.exists(sensor_path):
        raise NodewattsError(
            "Sensor config file missing at path: " + sensor_path)
    if not os.path.exists(sw_path):
        raise NodewattsError(
            "Smartwatts config file missing at path: " + sw_path
        )

    with open(sensor_path, "r") as f:
        try:
            sensor_raw = json.load(f)
        except json.decoder.JSONDecodeError as e:
            raise InvalidConfig(
                "Sensor config file must be in valid json format") from None
    NWConfig.validate_sensor_config(sensor_raw)

    with open(sw_path, "r") as f:
        try:
            sw_raw = json.load(f)
        except json.decoder.JSONDecodeError as e:
            raise InvalidConfig(
                "Smartwatts config file must be in valid json format") from None
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
            raise NodewattsError(
                "Error creating temp working directory: \n" + str(e))
    config.tmp_path = tmpPath
    proc_manager = SubprocessManager(config)
    profiler = ProfilerHandler(config, proc_manager)
    profiler.run_profiler()


if __name__ == "__main__":
    conf = NWConfig()
    parser = create_cli_parser()
    parser.parse_args(namespace=conf)
    NWConfig.validate_config_path(conf.config_file)
    try:
        raw = json.load(open(conf.config_file))
    except json.decoder.JSONDecodeError as e:
        raise InvalidConfig(
            "Configuration file must be in valid json format") from None
    NWConfig.validate(raw)
    conf.setup(raw)
    #sys.tracebacklimit = 0
    logger = log.setup_logger(conf.verbose, "Main")
    run(conf)
    logger.info("Profile generated! Exiting...")
    sys.exit(0)
