from .error import EngineError


class InvalidConfig(EngineError):
    def __init__(self, msg, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class Config:
    def __init__(self, params: dict = None):
        if params:
            if not params["internal_db_uri"]:
                self.internal_db_addr = "mongodb://localhost:27017"
            else:
                self.internal_db_addr = params["internal_db_uri"]
            if not params["export_raw"]:
                self.export_raw = False
            else:
                self.export_raw = True
            if not params["out_db_uri"]:
                self.out_db_addr = self.internal_db_addr
            else:
                self.out_db_addr = params["out_db_uri"]
            if not params["out_db_name"]:
                self.out_db_name = "nodewatts"
            else:
                self.out_db_name = params["out_db_name"]
            if not params["profile_title"]:
                raise InvalidConfig("profile_title not provided")
            else:
                self.profile_id = params["profile_id"]
            if not params["report_name"]:
                raise InvalidConfig("report_name must be provided")
            else:
                self.report_name = params["report_name"]
            if not params["sensor_start"]:
                raise InvalidConfig("sensor_start must be provided")
            else:
                self.sensor_start = params["sensor_start"]
            if not params["sensor_end"]:
                raise InvalidConfig("sensor_end must be provided")
            else:
                self.sensor_end = params["sensor_end"]
            if not params["verbose"]:
                self.verbose = False
            else:
                self.verbose = params["verbose"]
