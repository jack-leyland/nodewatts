from nodewatts.nwengine.db import DatabaseInterface, DatabaseError

class Database(DatabaseInterface):
    def __init__(self, internal_uri):
        super().__init__(internal_uri)
    
    def has_sensor_data(self) -> bool:
        self.connect()
        cnt = self.internal_client["nodewatts"]["sensor_raw"].count_documents({}) == 0
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