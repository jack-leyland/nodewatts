from nodewatts.db import DatabaseError
from smartwatts.__main__ import run_smartwatts, SmartwattsRuntimeException
from nodewatts.error import NodewattsError
from nodewatts.config import NWConfig
from nodewatts.db import Database
import logging
logger = logging.getLogger("Main")

class SmartwattsError(NodewattsError):
    def __init__(self, msg, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)   

class SmartwattsHandler():
    def __init__(self, config: NWConfig, db: Database):
        self.config = config.smartwatts_config
        if config.sw_verbose:
            self.config["verbose"] = True
        self.db = db
    
    def run_formula(self):
        logger.info("Computing process power model. This may take several minutes...")
        try:
            if not self.db.has_sensor_data():
                logger.error("Raw sensor data was not saved properly - Collection empty")
                raise SmartwattsError(None)
        except DatabaseError as e :
            logger.error(str(e))
            raise SmartwattsError(None) from None
        try:
            run_smartwatts(self.config, direct_call=True)
        except SmartwattsRuntimeException as e:
            #Expected when sigint or sigterm while smartwatts is running
            if e is None:
                pass
            else:
                logger.error("An error occured while running smartwatts formula. Message: " + str(e))
                raise SmartwattsError(None)
        logger.info("Power modelling complete.")
        
        

        

