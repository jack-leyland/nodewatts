from nwengine.db import Database
from nwengine.cpu_profile import CpuProfile
from nwengine.power_profile import PowerProfile
from nwengine.report import Report
import argparse
import logging
import sys

if __name__ == "__main__":
    class Config:
        pass

    config = Config()

    parser = argparse.ArgumentParser(description='internal argument interface for nodewatts')
    parser.add_argument('--internal_db_addr', type=str, default='localhost')
    parser.add_argument('--internal_db_port', type=int, default=27017)
    parser.add_argument('--export_raw', type=bool, default=False, required=False)
    parser.add_argument('--out_db_addr', type=str, default='localhost', required=False)
    parser.add_argument('--out_db_port', type=int, default=27017, required=False)
    parser.add_argument('--out_db_name', type=str, default="nodewatts", required=False)
    parser.add_argument('--profile_id', type=str, required=True)
    parser.add_argument('--report_name', type=str, required=True)
    parser.add_argument('--sensor_start', type=int, required=False)
    parser.add_argument('--sensor_end', type=int, required=False)
    parser.add_argument('--verbose', type=bool, required=True)

    parser.parse_args(namespace=config)

    logging.info("Nodewatts data processor started.")

    if config.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Defined error codes for the parent process?
    # MAYBE: add report format validator before saving 

    try:
        db = Database(config.internal_db_addr, config.internal_db_port)
    except Exception as e:
        logging.error("Failed to connect to internal database at %s, port %i", \
            config.internal_db_addr, config.internal_db_port, exec_info=True)
        sys.exit(-1)

    if config.export_raw:
        try:
            db.connect_to_export_db(config.out_db_addr, config.out_db_port, config.out_db_name)
        except Exception as e:
            logging.error("Failed to connect to export database at %s, port %i", \
            config.out_db_addr, config.out_db_port, exec_info=True)
        sys.exit(-1)

    # Calling programe will ensure that these collections are not empty before startign engine
    prof_raw = db.get_cpu_prof_by_id(config.profile_id)
    cpu = CpuProfile(prof_raw)

    if config.sensor_start and config.sensor_end:
        power_sample_start = config.sensor_start
        power_sample_end = config.sensor_end
    else:
        # May delete this fallback with further testing, more of a hack for development
        power_sample_start = cpu.start_time - 2000
        power_sample_end = cpu.end_time + 2000

    if power_sample_start > cpu.start_time or power_sample_end < cpu.end_time:
        logging.error("Insufficient sensor data to compute power report.")
        sys.exit(-1)

    power_raw = db.get_power_samples_by_range(power_sample_start, power_sample_end)

    try:
        power = PowerProfile(power_raw)
    except ValueError as e:
        logging.error(e)
        sys.exit(-1)

    report = Report(config.report_name, cpu, power)
    formatted = report.to_json()

    try:
        db.save_report(formatted)
    except Exception as e:
        logging.error("Failed to save report to internal database.")
        sys.exit(-1)

    if config.export_raw:
        try :
            db.export_report(formatted)
        except Exception as e:
            logging.warn("Failed to export raw data report.")
            sys.exit(-2)

    logging.info("Data processing complete.")
    sys.exit(0)