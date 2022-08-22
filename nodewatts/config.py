from nodewatts.nwengine.config import Config
from nodewatts.error import NodewattsError

from appdirs import AppDirs
from datetime import datetime
from pathlib import Path
import os
import json
import jsonschema as jschema
import platform
import logging
import sys
import shutil
logger = logging.getLogger("Main")


class InvalidConfig(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class NWConfig(Config):

    package_root = os.path.dirname(os.path.dirname(__file__))
    dirs = AppDirs("nodewatts", "Jack Leyland")
    if not os.path.exists(dirs.site_config_dir):
        logger.debug("Initializing config directory.")
        os.mkdir(dirs.site_config_dir)

    if not os.path.exists(dirs.site_data_dir):
        logger.debug("Initializing data directory.")
        os.mkdir(dirs.site_data_dir)

    def __init__(self):
        pass

    # Sets up config object instance with all parameters
    def populate(self, args: dict) -> None:

        ####
        # System Requirements
        ###

        if platform.system() != "Linux" and not self.visualizer:
            logger.error(
                "NodeWatts only works on Debian-based Linux Distributions")
            sys.exit(1)
        else:
            logger.info("Platform verified - Assuming Debian-based")

        if sys.version_info.major != 3 or sys.version_info.minor != 10:
            logger.error("NodeWatts requires Python 3.10 or above.")
            sys.exit(1)

        if not os.geteuid() == 0 and not self.visualizer:
            logger.error(
                "NodeWatts must be run as root to perform system power monitoring.")
            logger.info(
                "If you have installed nodewatts without root, please reinstall with sudo.")
            sys.exit(1)

        ####
        # Misc.
        ###

        self.tmp_path = None
        self.smartwatts_config = None
        self.viz_port = 8080
        self.profiler_port = 9999

        ####
        # Config Paths
        ###
        self.sensor_config_path = os.path.join(
            NWConfig.package_root, "resources/config/hwpc_config.json")
        self.sw_config_path = os.path.join(
            NWConfig.dirs.site_config_dir, "smartwatts_config.json")

        ####
        # Top-Level Config Options
        ###
        if "reportName" in args:
            if not isinstance(args["reportName"], str):
                raise InvalidConfig("reportName: expected string")
            self.report_name = args["reportName"]
        else:
            self.report_name = datetime.now().isoformat()

        if not isinstance(args["cpu-tdp"], int):
            raise InvalidConfig("cpu-tdp: expected int")
        else:
            self.cpu_tdp = args["cpu-tdp"]

        self.visualize = args["visualize"]
        if not isinstance(self.visualize, bool):
            raise InvalidConfig("visualize: expected bool")

        self.root_path = args["rootDirectoryPath"]
        if not isinstance(args["rootDirectoryPath"], str):
            raise InvalidConfig("rootDirectoryPath: expected string")

        self.entry_file = args["entryFile"]
        if not isinstance(args["entryFile"], str):
            raise InvalidConfig("entryFile: expected string")

        self.user = args["user"]
        if not isinstance(args["user"], str):
            raise InvalidConfig("user: expected string")

        if "nvm-node-version" in args:
            if not isinstance(args["nvm-node-version"], str):
                raise InvalidConfig("nvm-node-version: expected string")
            self.node_version = args["nvm-node-version"]
            nums = self.node_version.split(".")
            if len(nums) != 3:
                raise InvalidConfig(
                    "nvm-node-version: must provide full node version.")

        if "nvm-mode" in args:
            if not isinstance(args["nvm-mode"], bool):
                raise InvalidConfig("nvm-mode: expected bool")
            self.use_nvm = args["nvm-mode"]
        else:
            self.use_nvm = False

        if "es6-mode" in args:
            if not isinstance(args["es6-mode"], bool):
                raise InvalidConfig("es6-mode: expected bool")
            self.es6 = args["es6-mode"]
        else:
            self.es6 = False

        if "testRuns" in args:
            if not isinstance(args["testRuns"], int):
                raise InvalidConfig("testRuns: expected int")
            self.test_runs = args["testRuns"]
        else:
            self.test_runs = 3

        ####
        # Nested Options
        ###

        self.commands = args["commands"]
        if not isinstance(args["commands"]["serverStart"], str):
            raise InvalidConfig("serverStart: expected string")
        if not isinstance(args["commands"]["runTests"], str):
            raise InvalidConfig("runTests: expected string")

        ####
        # Developer Options
        ###

        if "dev-serverWait" in args:
            if not isinstance(args["dev-serverWait"], int):
                raise InvalidConfig("dev-serverWait: expected int")
            self.server_startup_wait = args["dev-serverWait"]
        else:
            self.server_startup_wait = 5

        if "dev-subprocessShell" in args:
            if not os.path.exists(args["dev-subprocessShell"]):
                raise InvalidConfig("Provided shell path does not exist")
            if not isinstance(args["dev-subprocessShell"], str):
                raise InvalidConfig("dev-subprocessShell: expected string")
            self.subprocess_shell_path = args["dev-subprocessShell"]
        else:
            self.subprocess_shell_path = "/bin/sh"

        if "dev-testRunnerTimeout" in args:
            if not isinstance(args["dev-testRunnerTimeout"], int):
                raise InvalidConfig("dev-testRunnerTimeout: expected int")
            self.test_runner_timeout = args["dev-testRunnerTimeout"]
        else:
            self.test_runner_timeout = 20

        if "dev-nvmPathOverride" in args:
            if not os.path.exists(args["dev-nvmPathOverride"]):
                raise InvalidConfig(
                    "Provided nvm override path does not exist.")
            self.override_nvm_path = args["dev-nvmPathOverride"]
        else:
            self.override_nvm_path = None

        if "dev-enableSmartWattsLogs" in args:
            if not isinstance(args["dev-enableSmartWattsLogs"], bool):
                raise InvalidConfig("dev-enableSmartWattsLogs: expected bool")
            self.sw_verbose = args["dev-enableSmartWattsLogs"]
        else:
            self.sw_verbose = False

        if self.visualize:
            viz_args = {
                "mongoUrl": self.engine_conf_args["internal_db_uri"],
                "port": self.viz_port
            }
            with (open(os.path.join(NWConfig.dirs.site_config_dir, "viz_config.json"), "w+")) as f:
                json.dump(viz_args, f)
        
        ####
        # Data Engine Args
        ###
        self.engine_conf_args = self._to_engine_format(args)


    # Validates and reports any missing required parameters
    @staticmethod
    def validate(args: dict) -> None:
        missing = {}
        if "rootDirectoryPath" not in args:
            missing["rootDirectoryPath"] = "[Absolute path to project root]"
        if "entryFile" not in args:
            missing["entryFile"] = "[Name of server entry file]"
        if "user" not in args:
            missing["user"] = "[System user used to interact with NodeJS]"
        if "nvm-mode" in args and "nvm-node-version" not in args:
            if args["nvm-mode"]:
                missing["nvm-node-version"] = [
                    "[Must specify full node version when nvm mode is enabled]"]
        if "database" not in args:
            missing["database"] = {
                "exportRawData": "[Boolean setting for exporting raw nodewatts data]",
                "exportUri": "[Required if exporting: MongoDB URI to send export]",
                "exportDbName": "[Required if exporting: Name of database to send export]"
            }
        else:
            if "exportRawData" not in args["database"]:
                if "database" not in missing:
                    missing["database"] = {
                        "exportRawData": "[Boolean setting for exporting raw nodewatts data]"}
                else:
                    missing["database"]["exportRawData"] = "[Boolean setting for exporting raw nodewatts data]"
            if "exportUri" not in args["database"]:
                if "database" not in missing:
                    missing["database"] = {
                        "exportUri": "[Required if exporting: MongoDB URI to send export]"}
                else:
                    missing["database"]["exportUri"] = "[Required if exporting: MongoDB URI to send export]"
            if "exportDbName" not in args["database"]:
                if "database" not in missing:
                    missing["database"] = {
                        "exportDbName": "[Required if exporting: Name of database to send export]"}
                else:
                    missing["database"]["exportDbName"] = "[Required if exporting: Name of database to send export]"
        if "visualize" not in args:
            missing["visualize"] = "[Boolean visualization output setting]"
        if "commands" not in args:
            missing["commands"] = {
                "serverStart": "[CLI command to start server]",
                "runTests": "[CLI command to run test suite]"
            }
        else:
            if "serverStart" not in args["commands"]:
                missing["commands"] = {
                    "serverStart": "[CLI command to start server]"
                }
            if "runTests" not in args["commands"]:
                if "commands" not in missing:
                    missing["commands"] = {
                        "runTests": "[CLI command to run test suite]"
                    }
                else:
                    missing["commands"]["runTests"] = "[CLI command to run test suite]"
        if "cpu-tdp" not in args:
            missing["cpu-tdp"] = "TDP of your CPU model"

        if len(missing) > 0:
            raise InvalidConfig(
                "Missing configuration fields: \n " + json.dumps(missing))

        if not os.path.exists(args["rootDirectoryPath"]):
            raise InvalidConfig("Root project path provided does not exist.")

        entry_path = os.path.join(args["rootDirectoryPath"], args["entryFile"])
        head_tail = os.path.split(entry_path)
        if not os.path.exists(entry_path):
            raise InvalidConfig(
                "Invalid path to entry file.")
        elif head_tail[1] is None:
            raise InvalidConfig("Entry file path provided is not a file.")

    @staticmethod
    def validate_config_path(conf_path: str) -> None:
        return os.path.exists(os.path.join(os.getcwd(), conf_path))

    def _to_engine_format(self, args: dict) -> dict:
        parsed = {}
        parsed["internal_db_uri"] = "mongodb://127.0.0.1:27017"
        parsed["export_raw"] = args["database"]["exportRawData"]
        if not isinstance(parsed["export_raw"], bool):
            raise InvalidConfig("Database: exportRawData: expected bool")
        parsed["out_db_uri"] = args["database"]["exportUri"]
        if not isinstance(parsed["out_db_uri"], str):
            raise InvalidConfig("Database: exportUri: expected string")
        parsed["verbose"] = self.verbose
        parsed["out_db_name"] = args["database"]["exportDbName"]
        if not isinstance(parsed["out_db_name"], str):
            raise InvalidConfig("Database: exportDbName: expected string")
        parsed["report_name"] = self.report_name
        parsed["outlier_limit"] = self.cpu_tdp
        return parsed

    def _generate_engine_conf(self, args: dict) -> Config:
        return super().__init__(args)

    # This will fail unless both module config files are validated beforehand
    def inject_config_vars(self):
        with open(self.sensor_config_path, "r+") as f:
            sensor = json.load(f)
            # Sensor verbose mode is not helpful in this context.
            sensor["verbose"] = False
            sensor["output"]["uri"] = self.engine_conf_args["internal_db_uri"]
            f.seek(0)
            json.dump(sensor, f)
            f.truncate()

        with open(self.sw_config_path, "r+") as f:
            sw = json.load(f)
            sw["cpu-tdp"] = self.cpu_tdp
            f.seek(0)
            json.dump(sw, f)
            f.truncate()

    @staticmethod
    def validate_sensor_config(args: dict) -> None:
        sensor_schema = {
            "type": "object",
            "required": ["name", "verbose", "frequency", "output", "system", "container"],
            "properties": {
                "name": {"type": "string"},
                "verbose": {"type": "boolean"},
                "frequency": {"type": "number"},
                "output": {
                    "type": "object",
                    "required": ["type", "uri", "database", "collection"],
                    "properties": {
                        "type": {"type": "string"},
                        "uri": {"type": "string"},
                        "database": {"type": "string"},
                        "collection": {"type": "string"}
                    }

                },
                "system": {
                    "type": "object",
                    "required": ["rapl", "msr"],
                    "properties": {
                        "rapl": {
                            "type": "object",
                            "required": ["events", "monitoring_type"],
                            "properties": {
                                "events": {"type": "array", "items": {"type": "string"}},
                                "monitoring_type": {"type": "string"}
                            },
                        },
                        "msr": {
                            "type": "object",
                            "required": ["events"],
                            "properties": {
                                "events": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    }
                },
                "container": {
                    "type": "object",
                    "required": ["core"],
                    "properties": {
                        "core": {
                            "type": "object",
                            "required": ["events"],
                            "properties": {
                                "events": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    }
                }
            }
        }

        try:
            jschema.validate(instance=args, schema=sensor_schema)
        except Exception as e:
            raise InvalidConfig(
                "Sensor configuration file is invalid: \n\n" + str(e)) from None

    @staticmethod
    def validate_smartwatts_config(args: dict) -> None:
        sw_schema = {
            "type": "object",
            "required": ["verbose", "stream", "input", "output", "cpu-frequency-base", "cpu-frequency-min", "cpu-frequency-max", "cpu-error-threshold",
                         "disable-dram-formula", "sensor-report-sampling-interval"],
            "properties": {
                "verbose": {"type": "boolean"},
                "stream": {"type": "boolean"},
                "input": {
                    "type": "object",
                    "required": ["puller"],
                    "properties": {
                        "puller": {
                            "type": "object",
                            "required": ["model", "type", "uri", "db", "collection"],
                            "properties": {
                                "model": {"type": "string"},
                                "type": {"type": "string"},
                                "uri": {"type": "string"},
                                "db": {"type": "string"},
                                "collection": {"type": "string"}
                            }
                        }
                    }

                },
                "output": {
                    "type": "object",
                    "required": ["pusher_power"],
                    "properties": {
                        "pusher_power": {
                            "type": "object",
                            "required": ["type", "uri", "db", "collection"],
                            "properties": {
                                "type": {"type": "string"},
                                "uri": {"type": "string"},
                                "db": {"type": "string"},
                                "collection": {"type": "string"}
                            }
                        }
                    }

                },
                "cpu-frequency-base": {"type": "integer"},
                "cpu-frequency-min": {"type": "integer"},
                "cpu-frequency-max": {"type": "integer"},
                "cpu-error-threshold": {"type": "number"},
                "disable-dram-formula": {"type": "boolean"},
                "sensor-report-sampling-interval": {"type": "integer"}
            }
        }

        try:
            jschema.validate(instance=args, schema=sw_schema)
        except Exception as e:
            raise InvalidConfig(
                "Smartwatts configuration file is invalid: \n Please ensure you \
                     have run the provided install.sh file. \n\n" + str(e)) from None
