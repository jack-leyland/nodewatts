import modules.nodewatts_data_engine.nwengine.log
from modules.nodewatts_data_engine.nwengine.config import Config
from nodewatts.error import NodewattsError
import os
import json
import jsonschema as jschema


class InvalidConfig(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class NWConfig(Config):
    def __init__(self):
        pass

    def setup(self, args: dict) -> None:
        self.verbose = args["verbose"]
        self.visualize = args["visualize"]
        self.root_path = args["rootDirectoryPath"]
        self.commands = args["commands"]
        self.entry_file = args["entryFile"]
        self.engine_conf_args = self._to_engine_format(args)

    @staticmethod
    def validate(args: dict) -> None:
        missing = {}
        if "rootDirectoryPath" not in args:
            missing["rootDirectoryPath"] = "[Absolute path to project root]"
        if "entryFile" not in args:
            missing["entryFile"] = "[Name of server entry file]"
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
        if "verbose" not in args:
            missing["verbose"] = "[Boolean debug level setting]"
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

    @staticmethod
    def validate_config_path(conf_path: str) -> None:
        if not os.path.exists(os.path.join(os.getcwd(), conf_path)):
            raise NodewattsError(
                "Configuration file does not exist at provided path")

    def _to_engine_format(self, args: dict) -> dict:
        parsed = {}
        parsed["internal_db_uri"] = args["database"]["uri"]
        parsed["export_raw"] = args["database"]["exportRawData"]
        parsed["out_db_uri"] = args["database"]["exportUri"]
        parsed["verbose"] = args["verbose"]
        parsed["out_db_name"] = args["database"]["exportDbName"]
        return parsed

    def _generate_engine_conf(self, args: dict) -> Config:
        return super().__init__(args)

    # This will fail unless both module config files are validated beforehand
    def inject_module_config_vars(self):
        with open(os.path.join(
            os.getcwd(), "./nodewatts/config/hwpc_config.json"), "r+"
        ) as f:
            sensor = json.load(f)
            sensor["verbose"] = self.verbose
            sensor["output"]["uri"] = self.engine_conf_args["internal_db_uri"]
            f.seek(0)
            json.dump(sensor, f)
            f.truncate()

        with open(os.path.join(
            os.getcwd(), "./nodewatts/config/smartwatts_config.json"), "r+"
        ) as f:
            smartwatts = json.load(f)
            smartwatts["verbose"] = self.verbose
            smartwatts["input"]["puller"]["uri"] = self.engine_conf_args["internal_db_uri"]
            smartwatts["output"]["pusher_power"]["uri"] = self.engine_conf_args["internal_db_uri"]
            f.seek(0)
            json.dump(smartwatts, f)
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
