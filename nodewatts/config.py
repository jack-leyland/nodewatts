from nwengine.config import Config

from nodewatts.error import NodewattsError

import os
import json
import jsonschema as jschema
import platform
import logging
import sys
logger = logging.getLogger("Main")


class InvalidConfig(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class NWConfig(Config):
    def __init__(self):
        pass

    def setup(self, args: dict) -> None:

        if platform.system() != "Linux":
            logger.error("NodeWatts only works on Debian-based Linux Distributions")
            sys.exit(1)
        else:
            logger.info("Platform verified - Assuming Debian-based")

        if not os.geteuid() == 0:
            logger.error("NodeWatts must be run as root to perform system power monitoring.")
            sys.exit(1)
        
        self.visualize = args["visualize"]
        if not isinstance(self.visualize, bool):
            raise InvalidConfig("visualize: expected bool")
        self.root_path = args["rootDirectoryPath"]
        self.commands = args["commands"]
        self.entry_file = args["entryFile"]
        self.user = args["user"]
        self.engine_conf_args = self._to_engine_format(args)
        self.sensor_config_path = os.path.join(
            os.getcwd(), "./nodewatts/config/hwpc_config.json")
        self.sw_config_path = os.path.join(
            os.getcwd(), "./nodewatts/config/smartwatts_config.json")


        if not isinstance(self.engine_conf_args["export_raw"], bool):
            raise InvalidConfig("Database: exportRawData: expected bool")
        self.tmp_path = None
        if "profilerPort" in args:
            self.profiler_port = int(args["profilerPort"])
        else:
            self.profiler_port = 9999
        if "dev-serverWait" in args:
            if not isinstance(args["dev-serverWait"], int):
                raise InvalidConfig("dev-serverWait: expected int")
            self.server_startup_wait = args["dev-serverWait"]
        else:
            self.server_startup_wait = 5
        if "dev-subprocessShell" in args:
            if not os.path.exists(args["dev-subprocessShell"]):
                raise InvalidConfig("Provided shell path does not exist")
            self.subprocess_shell_path = args["dev-subprocessShell"]
        else:
            self.subprocess_shell_path = "/bin/sh"
        if "dev-testRunnerTimeout" in args:
            if not isinstance(args["dev-testRunnerTimeout"], int):
                raise InvalidConfig("dev-testRunnerTimeout: expected int")
            self.test_runner_timeout = args["dev-testRunnerTimeout"]
        else:
            self.test_runner_timeout = 20
        if "nvm-mode" in args:
            if not isinstance(args["nvm-mode"], bool):
                raise InvalidConfig("nvm-mode: expected bool")
            self.use_nvm = args["nvm-mode"]
        else:
            self.use_nvm = False
        if "nvm-node-version" in args:
            self.node_version = args["nvm-node-version"]
            nums = self.node_version.split(".")
            if len(nums) != 3:
                raise InvalidConfig("nvm-node-version: must provide full node version.")
        if "dev-nvmPathOverride" in args:
            if not os.path.exists(args["dev-nvmPathOverride"]):
                raise InvalidConfig("Provided nvm override path does not exist.")
            self.override_nvm_path = args["dev-nvmPathOverride"]
        else:
            self.override_nvm_path = None

        self.smartwatts_config = None

        if "dev-enableSmartWattsLogs" in args:
            if not isinstance(args["dev-enableSmartWattsLogs"], bool):
                raise InvalidConfig("dev-enableSmartWattsLogs: expected bool")
            self.sw_verbose = args["dev-enableSmartWattsLogs"]
        else:
            self.sw_verbose = False
            
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
                missing["nvm-node-version"] = ["[Must specify full node version when nvm mode is enabled]"]
        if "profilerPort" in args and not isinstance(args["profilerPort"], int):
            raise InvalidConfig("profilerPort field expects integer.")
        if "database" not in args:
            missing["database"] = {
                "uri": "[MongoDB uri for internal nodewatts DB]",
                "exportRawData": "[Boolean setting for exporting raw nodewatts data]",
                "exportUri": "[Required if exporting: MongoDB URI to send export]",
                "exportDbName": "[Required if exporting: Name of database to send export]"
            }
        else:
            if "uri" not in args["database"]:
                missing["database"] = {
                    "uri": "[MongoDB uri for internal nodewatts DB]"}
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

        if len(missing) > 0:
            raise InvalidConfig(
                "Missing configuration fields: \n " + json.dumps(missing))

        if not os.path.exists(args["rootDirectoryPath"]):
            raise InvalidConfig("Root project path provided does not exist.")
        if not os.path.exists(os.path.join(args["rootDirectoryPath"], args["entryFile"])):
            raise InvalidConfig(
                "Entry file must be in root directory, or a relative path from the project root.")

    @staticmethod
    def validate_config_path(conf_path: str) -> None:
        return os.path.exists(os.path.join(os.getcwd(), conf_path))

    def _to_engine_format(self, args: dict) -> dict:
        parsed = {}
        parsed["internal_db_uri"] = args["database"]["uri"]
        parsed["export_raw"] = args["database"]["exportRawData"]
        parsed["out_db_uri"] = args["database"]["exportUri"]
        parsed["verbose"] = self.verbose
        parsed["out_db_name"] = args["database"]["exportDbName"]
        return parsed

    def _generate_engine_conf(self, args: dict) -> Config:
        return super().__init__(args)

    # This will fail unless both module config files are validated beforehand
    def inject_sensor_config_vars(self):
        with open(self.sensor_config_path, "r+") as f:
            sensor = json.load(f)
            sensor["verbose"] = False # Sensor verbose mode is not helpful in this context.
            sensor["output"]["uri"] = self.engine_conf_args["internal_db_uri"]
            f.seek(0)
            json.dump(sensor, f)
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
