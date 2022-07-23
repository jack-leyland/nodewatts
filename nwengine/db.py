import pymongo
from pymongo import MongoClient
import logging
from .error import EngineError
logger = logging.getLogger("Engine")


class DatabaseError(EngineError):
    def __init__(self, msg, *args, **kwargs):
        prefix = "Engine Database Error: "
        super().__init__(prefix + msg, *args, **kwargs)


class DatabaseInterface:
    def __init__(self, uri="mongodb://localhost:27017"):
        self.internal_uri = uri    
        self.export_client = None
        self.export_db = None
        self.internal_client = None
        self.internal_db = None
        

    def connect(self):
        self.internal_client = MongoClient(self.internal_uri, serverSelectionTimeoutMS=50)
        try:
            self.internal_client.admin.command('ismaster')
        except pymongo.errors.ServerSelectionTimeoutError as e:
            raise DatabaseError("Failed to connect to internal database at uri: " 
                                + self.internal_uri + "Error: " + str(e))
        else:
            logger.debug("Configured internal db mongo client at uri %s", self.internal_uri)

        self.internal_db = self.internal_client["nodewatts"]


    def connect_to_export_db(self, uri: str, name='nodewatts') -> None:
        self.export_client = MongoClient(uri, serverSelectionTimeoutMS=50)

        try:
            self.export_client.admin.command('ismaster')
        except pymongo.errors.ServerSelectionTimeoutError as e:
            raise DatabaseError("Failed to connect to export database at uri: " 
                                + uri + "Error: " + str(e))
        else:
            logger.debug("Configured export db mongo client at uri %s", uri)

        self.internal_db = self.export_client[name]

    def close_connections(self):
        if self.internal_client is not None:
            self.internal_client.close()
        if self.export_client is not None:
            self.export_client.close()
    


class EngineDB(DatabaseInterface):
    def __init__(self, internal_uri:str):
        super.__init__(self, internal_uri)
    
    # internal db name is not intended to be configurable
    def get_cpu_prof_by_title(self, title: str) -> dict:
        res = self.internal_db["cpu"].find_one({"title": title})
        return res

    def get_power_samples_by_range(self, start: int, end: int) -> dict:
        res = self.internal_db["power"].find({"timestamp":{"$gt": start, "$lt": end}}).sort("timestamp", 1)
        return res

    def save_report_to_internal(self, report: dict) -> None:
        self.internal_db["reports"].insert_one(report)

    def export_report(self, report: dict, ) -> None:
        self.export_db["nodewatts_exports"].insert_one(report)


