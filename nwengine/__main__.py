from . import __version__ as nwengine_version
from .db import EngineDB, DatabaseError, EngineDB
from .cpu_profile import CpuProfile
from .error import EngineError
from .power_profile import PowerProfile
from .report import Report
from .config import Config, InvalidConfig
from . import log
import argparse
import sys


def create_cli_parser():
    parser = argparse.ArgumentParser(
        description='internal argument interface for nodewatts')
    parser.add_argument('--internal_db_uri', type=str,
                        default="mongodb://localhost:27017")
    parser.add_argument('--export_raw', type=bool,
                        default=False, required=False)
    parser.add_argument('--out_db_uri', type=str,
                        default="mongodb://localhost:27017", required=False)
    parser.add_argument('--out_db_name', type=str,
                        default="nodewatts", required=False)
    parser.add_argument('--profile_title', type=str, required=True)
    parser.add_argument('--report_name', type=str, required=True)
    parser.add_argument('--sensor_start', type=int, required=True)
    parser.add_argument('--sensor_end', type=int, required=True)
    parser.add_argument('--verbose', type=bool, required=False, default=False)
    return parser


def run_engine(args: Config or dict) -> None:
    logger = log.setup_logger(config.verbose, "Engine")

    if not isinstance(args, Config):
        try : 
            config = Config(args)
        except InvalidConfig as e:
            logger.error("Invalid configuration : "+ str(e))
            raise EngineError(None) from None

    db = EngineDB(config.internal_db_addr)
    try:
        db.connect()
        if config.export_raw:
            db.connect_to_export_db(config.out_db_uri, config.out_db_name)
    except DatabaseError as e:
        logger.error("Database error: " + str(e))
        raise EngineError(None) from None
    
    prof_raw = db.get_cpu_prof_by_title(config.profile_title)
    
    if prof_raw is None:
        logger.error("Could not locate cpu profile data.")
        raise EngineError(None)
    
    cpu = CpuProfile(prof_raw)

    if config.sensor_start > cpu.start_time or config.sensor_end < cpu.end_time:
        logger.error("Insufficient sensor data to compute power report.")
        raise EngineError(None)
    
    # Slightly pad coundaraies for correlation purposes
    power_sample_start = config.sensor_start - 2000
    power_sample_end = config.sensor_end + 2000
    
    power_raw = db.get_power_samples_by_range(
        power_sample_start, power_sample_end)

    if power_raw is None:
        logger.error("Could not locate power sensor data.")
        raise EngineError(None)

    power = PowerProfile(power_raw)
    report = Report(config.report_name, cpu, power)
    formatted = report.to_json()
    db.save_report_to_internal(formatted)

    if config.export_raw:
        db.export_report(formatted)

    db.close_connections()
    logger.info("Data processing complete.")


if __name__ == "__main__":
    config = Config()
    parser = create_cli_parser()
    parser.parse_args(namespace=config)
    try: 
        run_engine(config)
    except EngineError as e:
        print(str(e))
        sys.exit(1)
    sys.exit(0)
