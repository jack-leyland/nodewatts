import statistics as stat
from bisect import bisect_left
from .error import EngineError
import logging
logger = logging.getLogger("Engine")

class PowerSample:
    def __init__(self, sample_raw: dict):
        self.timestamp = sample_raw["timestamp"]
        self.sensor_name = sample_raw["sensor"]
        self.target = sample_raw["target"]
        self.power_val_watts = sample_raw["power"]
        self._debug_metadata = sample_raw["metadata"]

class PowerProfile:
    def __init__(self, power_raw: dict, outlier_limit=85):
        self.cgroup_timeline = None
        self.cgroup_delta_stats = {}
        self._build_timelines(power_raw)
        self.estimate_count = len(self.cgroup_timeline)
        self._compute_deltas(self.cgroup_timeline)
        self.cgroup_timeline = self._clean_outliers(outlier_limit)
        logger.debug("Power profile processed.")

    def _build_timelines(self, power_raw: dict) -> None:
        cgroup = []
        for item in power_raw:
            if item["target"] == "/node":
                cgroup.append(PowerSample(item))

        if not cgroup:
            raise EngineError("Power profile contains no data on Node PID.")

        self.cgroup_timeline = cgroup

    # exists for accuracy testing and profile statistics
    # ignores first two deltas - time from init to first sample
    def _compute_deltas(self, series: list) -> None:
        prev = series[0].timestamp
        deltas = []
        for v in series:
            deltas.append(v.timestamp - prev)
            prev = v.timestamp
        self.cgroup_deltas = deltas

        self.cgroup_delta_stats["avg"] = stat.mean(deltas[2:])
        self.cgroup_delta_stats["med"] = stat.median(deltas[2:])
        self.cgroup_delta_stats["max"] = max(deltas[2:])
        self.cgroup_delta_stats["min"] = min(deltas[2:])
        cnt =0
        for n in deltas:
            if n > 1200:
                cnt+=1
        self.cgroup_delta_stats["above_1200mcs"] = cnt
        self.power_deltas = deltas
    
    def _clean_outliers(self, limit: int) -> None:
        cleaned = []
        for n in self.cgroup_timeline:
            if n.power_val_watts <= limit:
                cleaned.append(n)
        return cleaned

    #returns the closest sample to the given timestamp
    def get_nearest(self, ts: int) -> PowerSample:
        #Need python 3.10 for this to work
        pos = bisect_left(self.cgroup_timeline, ts, key=lambda x: x.timestamp)
        if pos == 0:
            return self.cgroup_timeline[0]
        if pos == len(self.cgroup_timeline):
            return self.cgroup_timeline[-1]
        before = self.cgroup_timeline[pos - 1]
        after = self.cgroup_timeline[pos]
        if after.timestamp - ts < ts - before.timestamp:
            return after
        else:
            return before