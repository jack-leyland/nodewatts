from pymongo import MongoClient
from bson.objectid import ObjectId
import logging

class Database:
    def __init__(self, addr='localhost', port=27017):
        #establish connection on construction
        self.internal_addr = addr
        self.internal_port = port
        self.internal_client = MongoClient(addr, port)
        logging.debug("Connection established to internal DB at %s, port %i", addr, port)

    #internal db name is not intended to be configurable 
    def get_cpu_prof_by_id(self, id: str) -> dict:
        objId = ObjectId(id)
        return self.internal_client["nodewatts"]["cpu"].find_one({"_id": objId})

    def get_power_samples_by_range(self, start: int, end:int ) -> dict:
        return self.internal_client["nodewatts"]["power"].find({"timestamp": {"$gt": start, "$lt": end}}).sort("timestamp", 1)
    
    def save_report_to_interal(self, report: dict) -> None:
        self.internal_client["nodewatts"]["reports"].insert_one(report)

    def export_report(self, report: dict, ) -> None:
        self.internal_client[self.export_db_name]["exports"].insert_one(report)

    def connect_to_export_db(self, addr: str, port: int, name='nodewatts') -> None:
        self.export_client = MongoClient(addr, port)
        self.export_db_name = name
        logging.debug("Connection established to export DB at %s, port %i", addr, port)
