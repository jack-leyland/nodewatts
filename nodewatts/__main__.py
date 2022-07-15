import modules.nodewatts_data_engine.nwengine.log as log
from .config import NWConfig, InvalidConfig
import os 
import sys
import argparse
import json

def create_cli_parser():
    parser = argparse.ArgumentParser(description='NodeWatts: Power profiling tool for NodeJS web servers')
    parser.add_argument('--config_file', type=str, required=True)
    return parser

def run(config: NWConfig):
    pass

if __name__ == "__main__":
    conf = NWConfig()
    parser = create_cli_parser()
    parser.parse_args(namespace=conf)
    NWConfig.validate_config_path(conf.config_file)
    try:
        raw = json.load(open(conf.config_file))
    except json.decoder.JSONDecodeError as e:
        raise InvalidConfig("Configuration file must be in valid json format") from None
    NWConfig.validate(raw)
    conf.setup(raw)
    if not conf.verbose:
        sys.tracebacklimit = 0
    logger = log.setup_logger(conf.verbose, "Main")
    logger.info("Configuration Successful - Starting NodeWatts")
    run(conf)
    logger.info("Profile generated! Exiting...")
    sys.exit(0)

