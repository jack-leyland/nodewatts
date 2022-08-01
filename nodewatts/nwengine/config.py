from .error import EngineError


class InvalidConfig(EngineError):
    def __init__(self, msg, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class Config:
    def __init__(self, params: dict = None):
        if params:
            if "internal_db_uri" not in params:
                self.internal_db_uri = "mongodb://localhost:27017"
            else:
                self.internal_db_uri = params["internal_db_uri"]
            if "export_raw" not in params:
                self.export_raw = False
            else:
                self.export_raw = True
            if "out_db_uri" not in params:
                self.out_db_uri = self.internal_db_uri
            else:
                self.out_db_uri = params["out_db_uri"]
            if "out_db_name" not in params:
                self.out_db_name = "nodewatts"
            else:
                self.out_db_name = params["out_db_name"]
            if "profile_title" not in params:
                raise InvalidConfig("profile_title not provided")
            else:
                self.profile_title = params["profile_title"]
            if "report_name" not in params:
                raise InvalidConfig("report_name must be provided")
            else:
                self.report_name = params["report_name"]
            if "sensor_start" not in params:
                raise InvalidConfig("sensor_start must be provided")
            else:
                self.sensor_start = params["sensor_start"]
            if "sensor_end" not in params:
                raise InvalidConfig("sensor_end must be provided")
            else:
                self.sensor_end = params["sensor_end"]
            if "verbose" not in params:
                self.verbose = False
            else:
                self.verbose = params["verbose"]
            if "outlier_limit" not in params:
                self.outlier_limit = 85
            else:
                self.outlier_limit = params["outlier_limit"]
