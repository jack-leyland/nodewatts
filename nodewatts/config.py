import modules.nodewatts_data_engine.nwengine.log
from modules.nodewatts_data_engine.nwengine.config import Config
from nodewatts.error import NodewattsError
import os
import json

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
        if "rootDirectoryPath" not in args.keys():
            missing["rootDirectoryPath"] = "[Absolute path to project root]"
        if "entryFile" not in args.keys():
            missing["entryFile"] = "[Name of server entry file]"
        if "database" not in args.keys():
            missing["database"] = "[Database configuration object]"
        if "verbose" not in args.keys():
            missing["verbose"] = "[Boolean debug level setting]"
        if "visualize" not in args.keys():
            missing["visualize"] = "[Boolean visualization output setting]"
        if "commands" not in args.keys():
            missing["commands"] ={
                "serverStart": "[CLI command to start server]",
                "runTests": "[CLI command to run test suite]"
            }
        else:
            if "serverStart" not in args["commands"]:
                missing["commands"] ={
                    "serverStart": "[CLI command to start server]"
                }
            if "runTests" not in args["commands"]:
                if "commands" not in missing.keys():
                    missing["commands"] ={
                        "runTests": "[CLI command to run test suite]"
                    }
                else:
                    missing["commands"]["runTests"] = "[CLI command to run test suite]"
        
        if len(missing) > 0:
            raise InvalidConfig("Missing configuration fields: \n " + json.dumps(missing))

    @staticmethod
    def validate_config_path(conf_path: str) -> None:
        if not os.path.exists(conf_path):
            raise NodewattsError("Configuration file does not exist at provided path")

    def _to_engine_format(self, args: dict) -> dict:
        parsed = {}
        if "address" in args["database"].keys():
            parsed["internal_db_addr"] = args["database"]["address"]
        if "port" in args["database"].keys():
            parsed["internal_db_port"] = args["database"]["port"]
        if "exportRawData" in args["database"].keys():
            parsed["export_raw"] = args["database"]["exportRawData"]
        if "exportAddress" in args["database"].keys():
            parsed["out_db_addr"] = args["database"]["exportAddress"]
        if "exportPort" in args["database"].keys():
            parsed["out_db_port"] = args["database"]["exportPort"]
        if "verbose" in args.keys():
            parsed["verbose"] = args["verbose"]
        return parsed

    def _generate_engine_conf(self, args: dict) -> Config:
        return super().__init__(args)
