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
    def __init__(self, power_raw: dict):
        self.cgroup_timeline = None
        self.cgroup_delta_stats = {}
        # These mostly here for analysis and debug, irrelevant for final output
        self._global_timeline = None
        self._rapl_timeline = None

        self._build_timelines(power_raw)
        self._compute_deltas(self.cgroup_timeline)
        logger.debug("Power profile processed.")

    def _build_timelines(self, power_raw: dict) -> None:
        cgroup = []
        global_s = []
        rapl = []
        for item in power_raw:
            if item["target"] == "system": #change to Node eventually
                cgroup.append(PowerSample(item))
            elif item["target"] == "rapl":
                rapl.append(PowerSample(item))
            elif item["target"] == "global":
                global_s.append(PowerSample(item))

        if not cgroup:
            raise EngineError("Power profile contains no data on Node PID.")

        self.cgroup_timeline = cgroup
        self._global_timeline = global_s
        self._rapl_timeline = rapl
        

    #exists for accuracy testing and profile statistics
    def _compute_deltas(self, series: list) -> None:
        prev = series[0].timestamp
        deltas = []
        for v in series:
            deltas.append(v.timestamp - prev)
            prev = v.timestamp
        self.cgroup_deltas = deltas

        self.cgroup_delta_stats["avg"] = stat.mean(deltas)
        self.cgroup_delta_stats["max"] = max(deltas)
        self.cgroup_delta_stats["min"] = max(deltas)

    #returns the closest sample to the given timestamp, favoring the smaller one in case of a tie
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