from .cpu_profile import CpuProfile, Sample
from .power_profile import PowerProfile, PowerSample
from networkx.readwrite import json_graph
from datetime import datetime
import statistics as stat
import scipy.stats as st
import numpy as np 
from matplotlib import pyplot as plt 
from bisect import bisect_left
import sys
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
        self.stats["cpu_samples"] = cpu_prof.sample_count
        self.stats["power_estimates_pre_clean_count"] = power_prof.estimate_count
        estimate_vals = []
        for n in power_prof.cgroup_timeline:
            estimate_vals.append(n.power_val_watts)
        self.stats["pre_clean_mean"] = stat.mean(estimate_vals)
        self.stats["pre_clean_med"] = stat.median(estimate_vals)
        self.stats["pre_clean_stdev"] = stat.stdev(estimate_vals)
        raw_dist = self._get_best_distribution(estimate_vals)
        self.stats["pre_clean_dist_eval"] = {
            "best_fit": raw_dist[0],
            "best_p": raw_dist[1],
            "best_params": raw_dist[2]
        }
        self.stats["zeros"] = 0
        try:
            while True:
                estimate_vals.remove(0.0)
                self.stats["zeros"] +=1
        except ValueError:
            pass
        self.stats["nozeros_mean"] = stat.mean(estimate_vals)
        self.stats["nozeros_med"] = stat.median(estimate_vals)
        self.stats["nozeros_stdev"] = stat.stdev(estimate_vals)
        dist = self._get_best_distribution(estimate_vals)
        self.stats["nozeros_dist_eval"] = {
            "best_fit": dist[0],
            "best_p": dist[1],
            "best_params": dist[2]
        }
        raw_diffs = []
        raw_already_assigned = []
        raw_reused_cnt = 0
        for n in cpu_prof.sample_timeline:
            power_sample = power_prof.get_nearest(n.cum_ts)
            raw_already_assigned.append(power_sample.timestamp)
            raw_diffs.append(abs(n.cum_ts - power_sample.timestamp))
            if n.cum_ts in raw_already_assigned:
                raw_reused_cnt+=1
        self.stats["pre_clean_assignments"] = {
            "max_diff": max(raw_diffs),
            "min_diff": min(raw_diffs),
            "avg_diff": stat.mean(raw_diffs),
            "reused_estimates": raw_reused_cnt
        }
        cleaned = self._clean_power_samples(power_prof)
        self.stats["cleaned_estimate_count"] = len(cleaned)

        report = []
        diffs = []
        already_assigned = []
        reused_cnt = 0
        for n in cpu_prof.sample_timeline:
            measurement = self._get_nearest_from_list(n.cum_ts, cleaned)
            power_sample = power_prof.get_nearest(measurement["timestamp"])
            diffs.append(abs(n.cum_ts - power_sample.timestamp))
            already_assigned.append(measurement["timestamp"])
            if n.cum_ts in already_assigned:
                reused_cnt+=1
            report.append(ProfileTick(n, power_sample))
            self.node_map[n.node_idx].append_pwr_measurement(power_sample.power_val_watts)
            self._assign_to_category(self.node_map[n.node_idx].call_frame["url"], n.node_idx)

        self.stats["post_clean_assignments"] = {
            "max_diff": max(diffs),
            "min_diff": min(diffs),
            "avg_diff": stat.mean(diffs),
            "reused_estimates": reused_cnt
        }
        self.chronological_report = report
        self.stats["sens_start"] = sys.maxsize *2 +1
        self.stats["sens_end"] = 0

        self.stats["cleaned_estiamtes_over_85"] = 0

        for i in cleaned:
            if i["power_val_watts"] > 85:
                self.stats["cleaned_estiamtes_over_85"] += 1
            if i["timestamp"] < self.stats["sens_start"]:
                self.stats["sens_start"] = i["timestamp"]
            if i["timestamp"] > self.stats["sens_end"]:
                self.stats["sens_end"] = i["timestamp"]
        self.stats["cpu_deltas"] = cpu_prof.cpu_deltas
        self.stats["power_deltas"] = power_prof.power_deltas


    def _clean_power_samples(self, power_prof: PowerProfile)->list:
        no_zeros = []
        all_measurements = [] 
        for n in power_prof.cgroup_timeline:
            all_measurements.append({
                "timestamp": n.timestamp,
                "power_val_watts": n.power_val_watts
            })
            if (n.power_val_watts) != 0:
                no_zeros.append({
                    "timestamp": n.timestamp,
                    "power_val_watts": n.power_val_watts
                })
        self.stats["estimates_over_time"] = all_measurements
        return no_zeros

    def _get_nearest_from_list(self, ts:int, list:list) -> float:
        pos = bisect_left(list, ts, key=lambda x: x["timestamp"])
        if pos == 0:
            return list[0]
        if pos == len(list):
            return list[-1]
        before = list[pos - 1]
        after = list[pos]
        if after["timestamp"] - ts < ts - before["timestamp"]:
            return after
        else:
            return before

    def plot_histogram(self, data):
        bin = []
        val = 0
        for i in range(0, 100):
            bin.append(val)
            val +=10
        a = np.array(data) 
        plt.hist(a, bins=bin) 
        plt.ylim(0, 1000)
        plt.title("histogram") 
        plt.show()

    def plot_lines(self, data):
        y = np.array(data) 
        x = np.arange(1, 5521)
        plt.plot(x, y, color ="green")
        plt.title("power deltas") 
        plt.show()

        
    def _get_best_distribution(self, measurements):
        data = measurements
        dist_names = ["norm", "exponweib", "weibull_max", "weibull_min", "pareto", "genextreme"]
        dist_results = []
        params = {}
        for dist_name in dist_names:
            dist = getattr(st, dist_name)
            param = dist.fit(data)
            params[dist_name] = param
            # Applying the Kolmogorov-Smirnov test
            D, p = st.kstest(data, dist_name, args=param)
            dist_results.append((dist_name, p))

        # select the best fitted distribution
        best_dist, best_p = (max(dist_results, key=lambda item: item[1]))
        # store the name of the best fit and its p value

        return [best_dist, best_p, params[best_dist]]


    # Convert entire report to JSON and return for db class to save
    def to_json(self):
        return json.loads(json.dumps(self, default=lambda x: x.__dict__))
    