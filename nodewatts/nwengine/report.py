from .cpu_profile import CpuProfile, Sample
from .power_profile import PowerProfile, PowerSample
from networkx.readwrite import json_graph
from datetime import datetime
import statistics as stat
import json
import logging
logger = logging.getLogger("Engine")

class ProfileTick:
    def __init__(self, cpu_sample_info: Sample, power_sample: PowerSample):
        self.cpu_sample_info = vars(cpu_sample_info)
        self.power_sample = vars(power_sample)

class CategorySummary:
    def __init__(self):
        self.node_js = {}
        self.npm_packages = {}
        self.user = []
        self.system = []

# Utility class that provides various parsing functionalty for callframe paths
class PathParser:
    @staticmethod
    def split_path(path: str) -> str:
        return path.split("/")
    
    @staticmethod
    def is_node_prefixed(path: str) -> bool:
        if not path: return False
        if path[0:5] == "node:": 
            return True
        else: return False
    
    @staticmethod
    def is_npm_package(path: str) -> bool:
        split = PathParser.split_path(path)
        if "node_modules" in split:
            return True
        else: return False

    @staticmethod
    def get_package_name(path: str) -> str:
        split = PathParser.split_path(path)
        if "node_modules" not in split: return ""
        return split[split.index("node_modules")+1]

class Report:
    def __init__(self, name,  cpu: CpuProfile, power: PowerProfile):
        logger.debug("Beginning report processing.")
        self.name = name
        self.engine_datetime = datetime.now().isoformat()
        self.node_map = cpu.node_map
        self.node_graph_json = json.dumps(json_graph.tree_data(cpu.node_dir_graph, root=1))
        self.chronological_report = None
        self.categories = CategorySummary()
        self.stats = {
            "power_deltas": power.cgroup_delta_stats,
            "cpu_deltas": cpu.delta_stats
        }

        self._build_reports(cpu, power)
        logger.debug("Report built.")


    def _assign_to_category(self, path: str, idx: int) -> None:
        if path == '':
            if idx not in self.categories.system:
                self.categories.system.append(idx)
            return 
        
        split = PathParser.split_path(path)
        if PathParser.is_node_prefixed(split[0]):
            if split[0] not in self.categories.node_js.keys():
                self.categories.node_js[split[0]] = [idx]
            elif idx not in self.categories.node_js[split[0]]:
                self.categories.node_js[split[0]].append(idx)
        elif PathParser.is_npm_package(path):
            pkg_name = PathParser.get_package_name(path)
            if pkg_name not in self.categories.npm_packages.keys():
                self.categories.npm_packages[pkg_name] = [idx]
            elif idx not in self.categories.npm_packages[pkg_name]:
                self.categories.npm_packages[pkg_name].append(idx)
        elif idx not in self.categories.user:
            self.categories.user.append(idx)
    
    def _build_reports(self, cpu_prof: CpuProfile, power_prof: PowerProfile) -> None:
        report = []
        diffs = []
        for n in cpu_prof.sample_timeline:
            power_sample = power_prof.get_nearest(n.cum_ts)
            report.append(ProfileTick(n, power_sample))
            self.node_map[n.node_idx].append_pwr_measurement(power_sample.power_val_watts)
            diffs.append(abs(n.cum_ts - power_sample.timestamp))
            self._assign_to_category(self.node_map[n.node_idx].call_frame["url"], n.node_idx)
        self.chronological_report = report
        self.stats["avg_ts_diff"] = stat.mean(diffs)
        self.stats["max_ts_diff"] = max(diffs)
        self.stats["min_ts_diff"] = min(diffs)


    # Convert entire report to JSON and return for db class to save
    def to_json(self):
        return json.loads(json.dumps(self, default=lambda x: x.__dict__))
    