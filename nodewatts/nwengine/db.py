from nodewatts.db import DatabaseInterface
import logging
logger = logging.getLogger("Engine")


class EngineDB(DatabaseInterface):
    def __init__(self, internal_uri: str):
        super().__init__(internal_uri)

    # internal db name is not intended to be configurable
    def get_cpu_prof_by_title(self, title: str) -> dict:
        res = self.internal_client["nodewatts"]["profiles"].find_one({
                                                                     "title": title})
        return res

    def get_power_samples_by_range(self, start: int, end: int) -> dict:
        res = self.internal_client["nodewatts"]["cpu"].find(
            {"timestamp": {"$gt": start, "$lt": end}}).sort("timestamp", 1)
        return res

    def save_report_to_internal(self, report: dict) -> None:
        self.internal_client["nodewatts"]["reports"].insert_one(report)

    def export_report(self, report: dict) -> None:
        self.export_client[self.external_db_name]["nodewatts_exports"].insert_one(
            report)
