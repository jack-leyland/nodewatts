import pymongo
from pymongo import MongoClient
from nodewatts.error import NodewattsError
import logging
logger = logging.getLogger("Main")


class DatabaseError(NodewattsError):
    def __init__(self, msg, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class DatabaseInterface:
    def __init__(self, uri="mongodb://localhost:27017"):
        self.internal_uri = uri
        self.export_client = None
        self.export_db = None
        self.internal_client = None
        self.internal_db = None

    def connect(self):
        self.internal_client = MongoClient(
            self.internal_uri, serverSelectionTimeoutMS=50)
        try:
            self.internal_client.admin.command('ismaster')
        except pymongo.errors.ServerSelectionTimeoutError as e:
            raise DatabaseError("Failed to connect to internal database at uri: "
                                + self.internal_uri + "Error: " + str(e))
        else:
            logger.debug(
                "Configured internal db mongo client at uri %s", self.internal_uri)

    def connect_to_export_db(self, uri: str, name='nodewatts') -> None:
        self.export_client = MongoClient(uri, serverSelectionTimeoutMS=50)

        try:
            self.export_client.admin.command('ismaster')
        except pymongo.errors.ServerSelectionTimeoutError as e:
            raise DatabaseError("Failed to connect to export database at uri: "
                                + uri + "Error: " + str(e))
        else:
            logger.debug("Configured export db mongo client at uri %s", uri)
        self.external_db_name = name

    def close_connections(self):
        if self.internal_client is not None:
            self.internal_client.close()
        if self.export_client is not None:
            self.export_client.close()


class Database(DatabaseInterface):
    def __init__(self, internal_uri):
        super().__init__(internal_uri)

    def has_sensor_data(self) -> bool:
        self.connect()
        cnt = self.internal_client["nodewatts"]["sensor_raw"].count_documents({
        }) == 0
        self.close_connections()
        return cnt == 0

    # Rather than having each component track and perform cleanup of
    # its raw data in the case of a crash. NodeWatts will simply check
    # the relevant collections and drop them at startup. They will also be dropped
    # at the end. Reports and Exports will always be preserved.
    def drop_raw_data(self):
        self.connect()
        self.internal_client["nodewatts"].drop_collection("sensor_raw")
        self.internal_client["nodewatts"].drop_collection("cpu")
        self.internal_client["nodewatts"].drop_collection("profiles")
        self.internal_client["nodewatts"].drop_collection("nodes")
        self.internal_client["nodewatts"].drop_collection("callframes")
        self.close_connections()
